"""
Measure discovery and filtering across large, sparsely influential values trees.
"""

import argparse
import copy
import itertools
import json
import random
import time
from collections import Counter
from pathlib import Path

from hypothesis_helm.benchmarking.charts.fixture import FixtureWorkspace, chart_path
from hypothesis_helm.benchmarking.charts.generator import generate
from hypothesis_helm.benchmarking.charts.structural_sparsity import PLACEMENTS, configure, expected
from hypothesis_helm.benchmarking.execution.provenance import code_digest
from hypothesis_helm.benchmarking.reporting.progress import BenchmarkProgress
from hypothesis_helm.benchmarking.studies.filtering import save
from hypothesis_helm.benchmarking.studies.matrix import STRATEGIES, bundle_key, measure
from hypothesis_helm.charts.model import Chart
from hypothesis_helm.execution.processes import Processes
from hypothesis_helm.reporting.budget import parse_time_limit
from hypothesis_helm.schemas.contracts import configuration_key, mapping, sequence


def reference(chart: Chart, spec: dict[str, object]) -> tuple[set[str], Counter[str]]:
    """
    Enumerate only the fixed four-variable domain, independently of production planning.

    Args:
        chart (Chart): Loaded shared chart with constant padding.
        spec (dict[str, object]): Active path definitions.

    Returns:
        tuple[set[str], Counter[str]]: Exact configuration identities and manifest multiplicities.
    """
    paths = [[str(key) for key in sequence(path)] for path in sequence(mapping(spec["structural_sparsity"])["active_paths"])]
    identities: set[str] = set()
    outcomes: Counter[str] = Counter()
    for bits in itertools.product((False, True), repeat=4):
        values = copy.deepcopy(chart.defaults)
        for path, bit in zip(paths, bits, strict=True):
            current = values
            for key in path[:-1]:
                current = mapping(current[key])
            current[path[-1]] = bit
        identities.add(configuration_key(values))
        outcomes[bundle_key(expected(values, spec))] += 1
    return identities, outcomes


def main(argv: list[str] | None = None, *, workspace: FixtureWorkspace | None = None) -> int:
    """
    Run paired structural sparsity cases with the ordinary benchmark filtering engine.

    Args:
        argv (list[str] | None): Explicit CLI arguments.
        workspace (FixtureWorkspace | None): Owner of the one reusable chart.

    Returns:
        int: Zero for complete or explicitly timed-out measurements, one for unexpected failures.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".cache/benchmarks/structural-sparsity"))
    parser.add_argument("--breadths", type=int, nargs="+", default=[50, 200, 800])
    parser.add_argument("--depths", type=int, nargs="+", default=[2, 8, 24])
    parser.add_argument("--placements", choices=PLACEMENTS, nargs="+", default=list(PLACEMENTS))
    parser.add_argument("--methods", choices=STRATEGIES, nargs="+", default=list(STRATEGIES))
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--time-limit", type=parse_time_limit, default=540)
    parser.add_argument("--helm", default="helm")
    parser.add_argument("--plot-only", action="store_true")
    args = parser.parse_args(argv)
    from hypothesis_helm.benchmarking.reporting.structural_sparsity import plot

    if args.plot_only:
        plot(args.output, mapping(json.loads((args.output / "results.json").read_text())))
        return 0
    if min(args.breadths) < 4 or min(args.depths) < 0 or max(args.depths) > 64 or args.repeats < 1 or not 0 < args.time_limit <= 540:
        parser.error("require breadth >= 4, depths 0..64, positive repeats, and execution time in (0, 9m]")
    if any(len(items) != len(set(items)) for items in (args.breadths, args.depths, args.placements, args.methods)):
        parser.error("sweep coordinates and methods must be unique")
    if (args.output / "results.json").exists():
        parser.error("choose a new output directory; retained measurements will not be overwritten")
    if workspace is None:
        with FixtureWorkspace() as owned:
            return main(argv, workspace=owned)
    args.output.mkdir(parents=True, exist_ok=True)
    metadata: dict[str, object] = {
        "code_sha256": code_digest(),
        "helm": Processes().run([args.helm, "version", "--short"], capture_output=True, check=True, timeout=30).stdout.strip(),
        "breadths": args.breadths,
        "depths": args.depths,
        "placements": args.placements,
        "methods": args.methods,
        "repeats": args.repeats,
        "seed": args.seed,
        "time_limit_seconds": args.time_limit,
        "status": "running",
        "time_limit_scope": "per method execution; generation, reference, discovery, planning and analysis excluded",
        "variable_fields": 4,
        "valid_inputs": 16,
        "erroneous_inputs": 7,
        "defects": 2,
    }
    rows: list[dict[str, object]] = []
    document: dict[str, object] = {"metadata": metadata, "rows": rows}
    total = len(args.breadths) * len(args.depths) * len(args.placements) * args.repeats * len(args.methods)
    failed = False
    with BenchmarkProgress("Structural sparsity") as progress:
        for breadth, depth, placement in itertools.product(args.breadths, args.depths, args.placements):
            case = f"breadth-{breadth}-depth-{depth}-{placement}"
            logical = args.output / "charts" / case
            generate(logical, input_complexity=4, output_bins=2, workspace=workspace)
            configure(logical, breadth, depth, placement, args.seed, workspace=workspace)
            path = chart_path(logical, workspace=workspace)
            spec = mapping(json.loads((path / "benchmark.json").read_text()))
            truth = reference(Chart.load(path), spec)
            settings = mapping(spec["structural_sparsity"])
            for repeat in range(args.repeats):
                methods = list(args.methods)
                random.Random(f"{args.seed}:{breadth}:{depth}:{placement}:{repeat}").shuffle(methods)
                for method in progress.track(iter(methods), total=total):
                    started = time.perf_counter()
                    chart = Chart.load(path)
                    discovery = time.perf_counter() - started
                    row = measure(
                        chart,
                        spec,
                        method,
                        level=2,
                        seed=args.seed + repeat,
                        limit=10000,
                        seconds=args.time_limit,
                        helm=args.helm,
                        reference=truth,
                        strength=4,
                        manifest_oracle=expected,
                    )
                    row.update(
                        case=case,
                        breadth=breadth,
                        depth=depth,
                        placement=placement,
                        repeat=repeat,
                        value_nodes=settings["value_nodes"],
                        active_density=settings["active_density"],
                        mean_path_distance=settings["mean_path_distance"],
                        max_path_distance=settings["max_path_distance"],
                        projection_components=settings["projection_components"],
                        discovery_seconds=discovery,
                        wall_seconds=discovery + float(str(row["total_seconds"])),
                        errors_missed=7 - int(str(row["erroneous_inputs_evaluated"])),
                    )
                    rows.append(row)
                    save(args.output, document)
                    print(
                        f"{len(rows)}/{total} {case} {method}: {row['wall_seconds']:.3f}s, "
                        f"{row['errors_missed']}/7 errors missed, {row['status']}",
                        flush=True,
                    )
                    failed |= row["status"] not in {"passed", "time-limit"}
    metadata["status"] = "failed" if failed else "complete"
    save(args.output, document)
    plot(args.output, document)
    return int(failed)


def verify(document: dict[str, object]) -> None:
    """
    Reject missing cells or inconsistent fixed-domain measurements before publication.

    Args:
        document (dict[str, object]): Completed structural sparsity ledger.

    Returns:
        None: Raises AssertionError when requested cells or conservation checks fail.
    """
    metadata = mapping(document["metadata"])
    assert metadata["status"] == "complete"
    rows = [mapping(row) for row in sequence(document["rows"])]
    expected_cells = set(
        itertools.product(
            sequence(metadata["breadths"]),
            sequence(metadata["depths"]),
            sequence(metadata["placements"]),
            sequence(metadata["methods"]),
            range(int(str(metadata["repeats"]))),
        )
    )
    assert len(rows) == len(expected_cells)
    assert {(row["breadth"], row["depth"], row["placement"], row["strategy"], row["repeat"]) for row in rows} == expected_cells
    for row in rows:
        assert row["status"] in {"passed", "time-limit"} and row["error"] is None
        assert row["valid_domain"] == 16
        assert 0 <= int(str(row["erroneous_inputs_evaluated"])) <= 7
        assert row["errors_missed"] == 7 - int(str(row["erroneous_inputs_evaluated"]))
        assert row["value_nodes"] == 1 + int(str(row["breadth"])) * (int(str(row["depth"])) + 5)
        assert 0 <= int(str(row["completed"])) <= int(str(row["selected"])) <= 16
        assert row["remaining"] == int(str(row["selected"])) - int(str(row["completed"]))
        assert row["status"] != "passed" or row["remaining"] == 0
