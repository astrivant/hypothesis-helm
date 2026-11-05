"""
Compare sensitivity-order sweeps and defect discovery across fixed structural charts.
"""

import argparse
import csv
import gzip
import itertools
import json
import random
import shutil
import time
from pathlib import Path

from attrs import asdict
from hypothesis_helm.charts.model import Chart
from hypothesis_helm.charts.testing.rendering import render
from hypothesis_helm.exceptions.execution import TimeLimitReached
from hypothesis_helm.execution.runtime.budget import execution_timer, parse_time_limit
from hypothesis_helm.execution.runtime.processes import Processes
from hypothesis_helm.schemas.contracts import configuration_key, mapping, sequence
from hypothesis_helm.schemas.generation.combinations import plan_interactions

from hypothesis_helm_benchmarking.charts.faults import Fault, write_faults
from hypothesis_helm_benchmarking.charts.fixture import FixtureWorkspace
from hypothesis_helm_benchmarking.charts.generator import generate
from hypothesis_helm_benchmarking.charts.ordering import nest_inputs
from hypothesis_helm_benchmarking.charts.structures import STRUCTURES
from hypothesis_helm_benchmarking.charts.workload import source_digest
from hypothesis_helm_benchmarking.execution.ordering import Observation, methods, replay
from hypothesis_helm_benchmarking.execution.provenance import code_digest
from hypothesis_helm_benchmarking.reporting.progress import BenchmarkProgress

__all__ = ("choose_faults", "main", "verify")


def choose_faults(chart: Chart, strength: int, count: int, seed: int) -> list[Fault]:
    """
    Sample reachable Boolean triggers independently of any traversal ranking.

    Args:
        chart (Chart): Flat shared structural fixture before nesting its input paths.
        strength (int): Highest injected trigger order.
        count (int): Number of defects per order.
        seed (int): Fixed fixture seed, separate from traversal repeats.

    Returns:
        list[Fault]: Unique reachable triggers that leave the baseline valid.
    """
    values = plan_interactions(chart.schema, strength).values
    names = [name for name, value in chart.defaults.items() if type(value) is bool]
    rng = random.Random(seed)
    defects = []
    for order in range(1, strength + 1):
        candidates = [
            dict(zip(group, pattern, strict=True))
            for group in itertools.combinations(names, order)
            for pattern in itertools.product((False, True), repeat=order)
            if any(pattern)
        ]
        rng.shuffle(candidates)
        accepted = 0
        for terms in candidates:
            defect = Fault(f"order{order}_bug{accepted + 1:02d}", terms)
            if not any(defect.active(value) for value in values):
                continue
            defects.append(defect)
            accepted += 1
            if accepted == count:
                break
        if accepted != count:
            raise ValueError(f"only {accepted} reachable order-{order} defects; lower --bugs-per-order")
    return defects


def verify(document: dict[str, object]) -> None:
    """
    Reject incomplete matrices, duplicate cases and inconsistent discovery curves.

    Args:
        document (dict[str, object]): Recorded fixture populations and per-trial traces.

    Returns:
        None: All comparisons cover the same inputs and defect identities within each chart.
    """
    metadata = mapping(document["metadata"])
    assert metadata["status"] == "complete"
    fixtures = mapping(document["fixtures"])
    assert set(fixtures) == set(sequence(metadata["structures"]))
    expected = {
        (structure, method, seed)
        for structure in fixtures
        for method in methods(int(str(metadata["permutations"])))
        for seed in sequence(metadata["seeds"])
    }
    rows = [mapping(row) for row in sequence(document["rows"])]
    assert len(rows) == len(expected)
    assert {(row["structure"], row["method"], row["seed"]) for row in rows} == expected
    for row in rows:
        fixture = mapping(fixtures[str(row["structure"])])
        bug_orders = mapping(fixture["bug_orders"])
        count = int(str(fixture["cases"]))
        trace = [mapping(point) for point in sequence(row["trace"])]
        assert row["status"] == "complete" and row["completed"] == row["planned"] == count == len(trace)
        assert row["total_bugs"] == row["found"] == len(bug_orders) > 0
        assert {point["case_id"] for point in trace} == set(range(count))
        assert [point["iteration"] for point in trace] == list(range(1, count + 1))
        assert trace[0]["case_id"] == 0
        found: set[str] = set()
        paths: set[str] = set()
        for point in trace:
            new = {str(bug) for bug in sequence(point["new_bugs"])}
            assert not (found & new) and new <= set(bug_orders)
            found.update(new)
            paths.update(json.dumps(path) for path in sequence(point["changed_paths"]))
            assert point["found"] == len(found) and point["distinct_paths"] == len(paths)
            assert sum(int(str(value)) for value in mapping(point["found_by_order"]).values()) == len(found)
        early = int(str(row["early_iteration"]))
        assert row["early_recall_percent"] == 100 * int(str(trace[early - 1]["found"])) / len(bug_orders)
        assert row["discovery_area_percent"] == 100 * sum(int(str(point["found"])) for point in trace) / (count * len(bug_orders))


def main(argv: list[str] | None = None, *, workspace: FixtureWorkspace | None = None) -> int:
    """
    Render a fixed population once per chart and compare evidence-limited scheduling.

    Args:
        argv (list[str] | None): Explicit command arguments or process arguments.
        workspace (FixtureWorkspace | None): Owner of the shared physical chart.

    Returns:
        int: Zero after verified plots, or 124 when the measurement budget is exhausted.
    """
    from hypothesis_helm_benchmarking.reporting.ordering import publish

    if workspace is None:
        with FixtureWorkspace() as owned:
            return main(argv, workspace=owned)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=int, default=8, help="six to ten finite fields, held fixed throughout each sweep")
    parser.add_argument("--permutations", type=int, default=3, help="p: interaction strength and maximum sensitivity order")
    parser.add_argument("--repeats", type=int, default=5, help="paired traversal seeds; fixture and bugs stay fixed")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--bugs-per-order", type=int, default=2)
    parser.add_argument("--structures", nargs="+", choices=STRUCTURES, default=list(STRUCTURES))
    parser.add_argument("--time-limit", type=parse_time_limit, default=540, help="measurement budget per chart, including ordering replay")
    parser.add_argument("--helm", default="helm")
    parser.add_argument("--output", type=Path, default=Path(".cache/benchmarks/sensitivity-ordering"))
    parser.add_argument("--plot-only", action="store_true", help="redraw saved measurements without invoking Helm")
    args = parser.parse_args(argv)
    if args.plot_only:
        saved = mapping(json.loads((args.output / "results.json").read_text()))
        verify(saved)
        publish(args.output, saved)
        return 0
    if not 6 <= args.inputs <= 10 or not 1 <= args.permutations <= min(6, args.inputs - 1):
        parser.error("require 6 <= inputs <= 10 and 1 <= permutations <= min(6, inputs - 1)")
    if args.repeats < 1 or args.bugs_per_order < 1 or len(set(args.structures)) != len(args.structures):
        parser.error("repeats and bugs-per-order must be positive; structures must be unique")
    helm = shutil.which(args.helm)
    if helm is None:
        parser.error("Helm is required")
    if (args.output / "results.json").exists():
        parser.error("choose a fresh --output directory, or use --plot-only to redraw retained results")
    args.output.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    fixtures: dict[str, object] = {}
    metadata: dict[str, object] = {
        "status": "running",
        "code_sha256": code_digest(),
        "helm": Processes().run([helm, "version", "--short"], capture_output=True, check=True, timeout=30).stdout.strip(),
        "permutations": args.permutations,
        "inputs": args.inputs,
        "repeats": args.repeats,
        "seed": args.seed,
        "seeds": list(range(args.seed, args.seed + args.repeats)),
        "bugs_per_order": args.bugs_per_order,
        "structures": args.structures,
        "methods": methods(args.permutations),
        "time_limit_seconds": args.time_limit,
        "time_limit_scope": "per chart: reference renders and all ordering replays",
        "method": "real Helm outputs, deterministic scheduling replay; no fresh runtime claims",
        "selection": "same finite plan for every method; pruning, sampling and failure expansion disabled",
        "zero_order": "seeded random traversal without sensitivity profiling",
    }
    document: dict[str, object] = {"metadata": metadata, "fixtures": fixtures, "rows": rows}
    try:
        for structure in args.structures:
            logical = args.output / "cases" / structure
            generate(logical, input_complexity=args.inputs, output_bins=4, structure=structure, workspace=workspace)
            defects = choose_faults(Chart.load(workspace.chart), args.permutations, args.bugs_per_order, args.seed)
            write_faults(logical, defects, workspace=workspace, symbolic=True)
            paths = nest_inputs(logical, workspace=workspace)
            chart = Chart.load(workspace.chart)
            plan = plan_interactions(chart.schema, args.permutations)
            baseline = configuration_key(chart.defaults)
            values = [chart.defaults, *(value for value in plan.values if configuration_key(value) != baseline)]
            bug_orders = {bug.name: len(bug.terms) for bug in defects}
            fixtures[structure] = {
                "cases": len(values),
                "bug_orders": bug_orders,
                "paths": paths,
                "chart_sha256": source_digest(chart.path),
                "planner": plan.strategy,
                "effective_strength": plan.strength,
            }
            (args.output / f"{structure}-chart.json").write_text(
                json.dumps(
                    {str(path.relative_to(chart.path)): path.read_text() for path in sorted(chart.path.rglob("*")) if path.is_file()},
                    indent=2,
                )
                + "\n"
            )
            observations: list[Observation] = []
            deadline = time.monotonic() + args.time_limit

            def tick(deadline: float = deadline) -> float:
                """
                Check the shared render and scheduling deadline.

                Args:
                    deadline (float): Fixed end time for this chart.

                Returns:
                    float: Remaining measurement seconds.
                """
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeLimitReached()
                return remaining

            with gzip.open(args.output / f"{structure}-observations.json.gz", "wt") as evidence:
                with execution_timer(args.time_limit), BenchmarkProgress(f"Ordering: render {structure}") as progress:
                    for value in progress.track(values):
                        started = time.perf_counter()
                        resources = render(chart, value, helm=helm, release="ordering", timeout=min(30, tick()))
                        elapsed = time.perf_counter() - started
                        data = mapping(next(item for item in resources if mapping(item["metadata"])["name"] == "injected-faults")["data"])
                        flat: dict[str, object] = {}
                        for name, path in paths.items():
                            node: object = value
                            for part in path:
                                node = mapping(node)[part]
                            flat[name] = node
                        found = tuple(sorted(name for name, status in data.items() if status == "incorrect"))
                        expected = tuple(sorted(bug.name for bug in defects if bug.active(flat)))
                        assert found == expected, (structure, value, found, expected)
                        item = Observation(value, resources, found, elapsed)
                        observations.append(item)
                        evidence.write(json.dumps(asdict(item)) + "\n")
                with execution_timer(tick()), BenchmarkProgress(f"Ordering: compare {structure}") as progress:
                    trials = list(itertools.product(methods(args.permutations), range(args.seed, args.seed + args.repeats)))
                    for method, seed in progress.track(trials):
                        rows.append({"structure": structure, **replay(observations, bug_orders, method, seed, tick)})
            (args.output / "results.json").write_text(json.dumps(document, indent=2) + "\n")
        metadata["status"] = "complete"
    except TimeLimitReached:
        metadata["status"] = "time-limit"
    finally:
        (args.output / "results.json").write_text(json.dumps(document, indent=2) + "\n")
    if metadata["status"] != "complete":
        print(f"Incomplete measurements retained at {args.output}; no completed plots published.")
        return 124
    verify(document)
    fields = ["structure", "method", "seed", "planned", "found", "total_bugs", "early_recall_percent", "discovery_area_percent"]
    with (args.output / "results.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    publish(args.output, document)
    print(f"Ordering study: {args.output / 'README.md'}")
    return 0
