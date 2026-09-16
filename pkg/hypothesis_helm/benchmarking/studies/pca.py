"""
Compare output-space PCA before and after trimming with seeded five-percent input faults.
"""

import argparse
import json
import logging
import platform
import shutil
import time
from collections.abc import Sequence
from pathlib import Path

from hypothesis_helm.benchmarking.analysis.pca import inject_errors, project
from hypothesis_helm.benchmarking.analysis.selection import PRESETS
from hypothesis_helm.benchmarking.analysis.selection import select as select_preset
from hypothesis_helm.benchmarking.charts.fixture import FixtureWorkspace, chart_path
from hypothesis_helm.benchmarking.charts.generator import generate
from hypothesis_helm.benchmarking.charts.structures import STRUCTURES, configmap, expected_manifests
from hypothesis_helm.benchmarking.charts.workload import source_digest
from hypothesis_helm.benchmarking.execution.profiling import profile_settings
from hypothesis_helm.benchmarking.execution.provenance import code_digest
from hypothesis_helm.benchmarking.reporting.progress import BenchmarkProgress
from hypothesis_helm.benchmarking.studies.matrix import bundle_key, reference_space
from hypothesis_helm.charts.model import Chart
from hypothesis_helm.charts.rendering import render
from hypothesis_helm.compiler.passes.expansion import FailureExpansion
from hypothesis_helm.compiler.passes.topology import trim_topology
from hypothesis_helm.execution.processes import Processes
from hypothesis_helm.reporting.budget import TimeLimitReached, execution_timer, parse_time_limit
from hypothesis_helm.schemas.combinations import plan_interactions, trim_values
from hypothesis_helm.schemas.contracts import configuration_key, mapping
from hypothesis_helm.schemas.model import ValuesModel


def selections(
    chart: Chart, values: list[dict[str, object]], level: int, seed: int, *, strength: int = 2
) -> tuple[dict[str, list[int]], dict[str, object]]:
    """
    Apply production trimming to the faulty chart, retaining the default once.

    Args:
        chart (Chart): Fixture with faults already present in its templates.
        values (list[dict[str, object]]): Complete valid domain with defaults first.
        level (int): Quarter-retention depth for each enabled trim.
        seed (int): Common selector seed independent of error placement.
        strength (int): Interaction strength of the supplied plan for calibration matching.

    Returns:
        tuple[dict[str, list[int]], dict[str, object]]:
            Selected indices and conservative topology evidence.
    """
    positions = {configuration_key(value): index for index, value in enumerate(values)}
    candidates = values[1:]
    groups = {"before": list(range(len(values)))}
    evidence: dict[str, object] = {}
    selected: Sequence[dict[str, object]]
    for strategy in ("random", "topology", "combined", *PRESETS):
        if strategy in PRESETS:
            selected, evidence[strategy] = select_preset(chart, candidates, strategy, seed, strength=strength)
        elif strategy == "random":
            selected = trim_values(candidates, level, seed)
        else:
            selected, evidence[strategy] = trim_topology(
                chart.path,
                chart.defaults,
                candidates,
                candidates,
                level,
                seed,
                random_steps=level if strategy == "combined" else 0,
            )
        groups[strategy] = [0, *(positions[configuration_key(value)] for value in selected)]
    return groups, evidence


def expand_selections(
    chart: Chart,
    values: list[dict[str, object]],
    selected: dict[str, list[int]],
    bundles: list[list[dict[str, object]]],
) -> dict[str, int]:
    """
    Replay observed failures in order to include each preset's failure expansion in PCA.

    Args:
        chart (Chart): Faulty chart whose complete population was verified with Helm.
        values (list[dict[str, object]]): Complete reference configurations.
        selected (dict[str, list[int]]): Initial indices, extended in place for public presets.
        bundles (list[list[dict[str, object]]]): Actual rendered outputs, consulted only when a case is visited.

    Returns:
        dict[str, int]: Additional scheduled checks per preset; every retained index is unique.
    """
    added: dict[str, int] = {}
    for strategy in PRESETS:
        queue = selected[strategy]
        scheduler = FailureExpansion.build(chart.path, chart.defaults, values, values, queue)
        for index in queue:
            failed = any(
                mapping(resource.get("metadata", {})).get("name") == "benchmark-error"
                and mapping(resource.get("data", {})).get("status") == "incorrect"
                for resource in bundles[index]
            )
            if failed:
                queue.extend(scheduler.failed(index))
        added[strategy] = len(scheduler.added)
    return added


def run_case(
    output: Path,
    structure: str,
    complexity: int,
    percent: float,
    error_seed: int,
    seed: int,
    level: int,
    helm: str,
    seconds: float,
    *,
    topology_components: int = 0,
    topology_weights: dict[str, float] | None = None,
    topology_seed: int = 2026,
    topology_depth_weights: dict[int, float] | None = None,
    workspace: FixtureWorkspace | None = None,
) -> dict[str, object]:
    """
    Render the complete faulty fixture once, then compare selector subsets in a fixed projection.

    Args:
        output (Path): Study destination containing generated charts.
        structure (str): Structural category.
        complexity (int): Number of declared input fields.
        percent (float): Uniformly placed error percentage over valid assignments.
        error_seed (int): Independent fault seed.
        seed (int): Trimming seed.
        level (int): Depth for each enabled trim strategy.
        helm (str): Pinned Helm executable.
        seconds (float): Execution ceiling for the complete reference render.
        topology_components (int): Sampled component count, replacing the isolated structure.
        topology_weights (dict[str, float] | None): Mixture category weights, or uniform.
        topology_seed (int): Seed for mixture type and wiring placement.
        topology_depth_weights (dict[int, float] | None): Distribution of added gate depths.
        workspace (FixtureWorkspace | None): Explicit owner of the invocation's reusable chart.

    Returns:
        dict[str, object]: Exact observations, fitted basis, selection statistics and provenance.
    """
    path = output / "charts" / structure
    spec = generate(
        path,
        input_complexity=complexity,
        output_bins=4,
        structure=None if topology_components else structure,
        topology_components=topology_components,
        topology_weights=topology_weights,
        topology_seed=topology_seed,
        topology_depth_weights=topology_depth_weights,
        workspace=workspace,
    )
    chart = Chart.load(chart_path(path, workspace=workspace))
    truth, _ = reference_space(chart, spec, 8192)
    plan = plan_interactions(ValuesModel.from_schema(chart.schema), complexity, max_cases=8192, max_candidates=8192)
    baseline = configuration_key(chart.defaults)
    values = [
        chart.defaults,
        *(value for value in plan.values if configuration_key(value) != baseline),
    ]
    if {configuration_key(value) for value in values} != truth or len(values) != len(truth):
        raise AssertionError("planner and independent finite-domain oracle disagree")
    faulty = inject_errors(path, values, percent, error_seed, workspace=workspace)
    chart = Chart.load(chart_path(path, workspace=workspace))
    selected, evidence = selections(chart, values, level, seed)
    bundles: list[list[dict[str, object]]] = []
    started = time.perf_counter()
    status = "complete"
    try:
        with execution_timer(seconds):
            with BenchmarkProgress(f"{structure}: reference renders") as display:
                for index, value in enumerate(display.track(values)):
                    remaining = seconds - (time.perf_counter() - started)
                    if remaining <= 0:
                        raise TimeLimitReached()
                    actual = render(chart, value, helm=helm, release="matrix", timeout=min(30, remaining))
                    expected = [
                        *expected_manifests(value, spec),
                        configmap(
                            "benchmark-error",
                            {"status": "incorrect" if index in faulty else "expected"},
                        ),
                    ]
                    if bundle_key(actual) != bundle_key(expected):
                        raise AssertionError(f"independent fault/manifest oracle mismatch: {structure} input {index}")
                    bundles.append(actual)
                    if len(bundles) % 100 == 0:
                        print(f"  {structure}: {len(bundles)}/{len(values)} reference renders", flush=True)
    except TimeLimitReached:
        status = "time-limit"
    elapsed = time.perf_counter() - started
    row: dict[str, object] = {
        "structure": structure,
        "status": status,
        "valid_inputs": len(values),
        "completed": len(bundles),
        "remaining": len(values) - len(bundles),
        "execution_seconds": elapsed,
        "time_limit_seconds": seconds,
        "faulty_indices": sorted(faulty),
        "actual_error_percent": 100 * len(faulty) / len(values),
        "chart_sha256": source_digest(chart.path),
        "topology": evidence,
        "values": values,
        "selected_indices": selected,
        "initial_selected_indices": {strategy: list(indices) for strategy, indices in selected.items()},
    }
    if status != "complete":
        return row
    row["failure_expansion"] = expand_selections(chart, values, selected, bundles)
    coordinates, basis = project(bundles)
    keys = [bundle_key(bundle) for bundle in bundles]
    outcomes = sorted(set(keys))
    identities = {key: index for index, key in enumerate(outcomes)}
    row.update(
        {
            "pca": basis,
            "coordinates": coordinates.tolist(),
            "outcomes": [json.loads(key) for key in outcomes],
            "outcome_indices": [identities[key] for key in keys],
            "strategies": {
                strategy: {
                    "retained": len(indices),
                    "errors_detected": len(set(indices) & faulty),
                    "errors_missed": len(faulty - set(indices)),
                    "error_recall": len(set(indices) & faulty) / len(faulty) if faulty else None,
                    "output_coverage": len({keys[index] for index in indices}) / len(outcomes),
                }
                for strategy, indices in selected.items()
            },
        }
    )
    return row


def main(argv: list[str] | None = None, *, workspace: FixtureWorkspace | None = None) -> int:
    """
    Generate measured PCA comparisons without changing historical benchmark results.

    Args:
        argv (list[str] | None): Explicit command arguments or the process command line.
        workspace (FixtureWorkspace | None): Explicit owner of the invocation's reusable chart.

    Returns:
        int: Zero for a complete study; one when a reference population hits its deadline.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".cache/benchmarks/pca"))
    parser.add_argument("--input-complexity", type=int, default=10)
    parser.add_argument("--error-percent", type=float, default=5.0)
    parser.add_argument("--error-seed", type=int, default=1729)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--trim-level", type=int, default=2)
    parser.add_argument("--time-limit", type=parse_time_limit, default=540.0)
    parser.add_argument("--helm", default="helm")
    parser.add_argument("--plot-only", action="store_true")
    args = parser.parse_args(argv)
    from hypothesis_helm.benchmarking.reporting.pca import plot

    if args.plot_only:
        plot(args.output, mapping(json.loads((args.output / "results.json").read_text())))
        return 0
    if not (6 <= args.input_complexity <= 12 and 0 <= args.error_percent <= 100 and args.trim_level >= 0 and 0 < args.time_limit <= 540):
        parser.error("require 6..12 inputs, 0..100% errors, nonnegative trim level, and time limit <=9m")
    helm = shutil.which(args.helm)
    if helm is None:
        parser.error("Helm is required")
    if (args.output / "results.json").exists():
        parser.error("output already contains results; choose another directory")
    args.output.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.WARNING)
    rows: list[dict[str, object]] = []
    document: dict[str, object] = {
        "metadata": {
            "profiling": profile_settings(),
            "helm": Processes().run([helm, "version", "--short"], capture_output=True, check=True, timeout=30).stdout.strip(),
            "python": platform.python_version(),
            "code_sha256": code_digest(),
            "input_complexity": args.input_complexity,
            "error_percent": args.error_percent,
            "error_seed": args.error_seed,
            "seed": args.seed,
            "trim_level": args.trim_level,
            "time_limit_seconds": args.time_limit,
            "method": (
                "real full-population Helm renders checked "
                "against independent oracle; production selectors on "
                "faulty chart; one fixed PCA basis per category"
            ),
            "errors": (
                "uniform sample without replacement over valid "
                "input assignments, rounded down; visible incorrect "
                "status; error-case recall is not distinct-bug recall"
            ),
            "execution": (
                "render full population once, reuse observations "
                "for each selected subset; no per-strategy timing claims; "
                "deadline excludes planning, selection and PCA"
            ),
        },
        "rows": rows,
    }
    for structure in STRUCTURES:
        print(
            f"{structure}: render full population with {args.error_percent:g}% seeded errors",
            flush=True,
        )
        row = run_case(
            args.output,
            structure,
            args.input_complexity,
            args.error_percent,
            args.error_seed,
            args.seed,
            args.trim_level,
            helm,
            args.time_limit,
            workspace=workspace,
        )
        rows.append(row)
        temporary = args.output / "results.tmp"
        temporary.write_text(json.dumps(document, indent=2) + "\n")
        temporary.replace(args.output / "results.json")
        if row["status"] != "complete":
            print(f"Reference incomplete: {row['completed']}/{row['valid_inputs']}; saved stats without fitting partial PCA.")
            return 1
        print(f"  complete in {row['execution_seconds']:.1f}s: {row['strategies']}", flush=True)
    plot(args.output, document)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
