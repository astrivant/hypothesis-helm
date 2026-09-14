"""
Measure paired runtime and missed-error response surfaces at a fixed finite input-space size.
"""

import argparse
import hashlib
import itertools
import json
import math
import random
from functools import partial
from pathlib import Path

from hypothesis_helm.benchmarking.charts.error_surface import ErrorPopulation, configure_surface
from hypothesis_helm.benchmarking.charts.fixture import FixtureWorkspace, chart_path
from hypothesis_helm.benchmarking.charts.generator import generate
from hypothesis_helm.benchmarking.execution.profiling import profile_settings
from hypothesis_helm.benchmarking.execution.provenance import code_digest
from hypothesis_helm.benchmarking.reporting.progress import BenchmarkProgress
from hypothesis_helm.benchmarking.studies.error_surface import METHODS, RATES, save
from hypothesis_helm.benchmarking.studies.error_surface import verify as verify_pairing
from hypothesis_helm.benchmarking.studies.matrix import measure, reference_space
from hypothesis_helm.charts.model import Chart
from hypothesis_helm.execution.processes import Processes
from hypothesis_helm.reporting.budget import parse_time_limit
from hypothesis_helm.schemas.contracts import configuration_key, mapping, sequence

REFERENCE = "https://www.itl.nist.gov/div898/handbook/pri/section3/pri336.htm"


def verify(document: dict[str, object]) -> None:
    """
    Verify every requested cell and repeat, using the shared error-population accounting contract.

    Args:
        document (dict[str, object]): Completed study ledger.

    Returns:
        None: Missing cells, duplicate measurements and inconsistent populations raise assertions.
    """
    metadata = mapping(document["metadata"])
    cells = [mapping(cell) for cell in sequence(metadata["cells"])]
    rows = [mapping(row) for row in sequence(document["rows"])]
    expected = {
        (cell["id"], repeat, method)
        for cell in cells
        for repeat in range(int(str(metadata["repeats"])))
        for method in sequence(metadata["methods"])
    }
    assert len({cell["id"] for cell in cells}) == len(cells)
    assert len(rows) == len(expected)
    assert {(row["case"], row["repeat"], row["strategy"]) for row in rows} == expected
    for cell in cells:
        selected = [row for row in rows if row["case"] == cell["id"]]
        assert all(
            all(
                row[key] == cell[key]
                for key in ("plane", "x", "y", "condition_depth", "quantile_unused_inputs", "error_percent", "clustering")
            )
            for row in selected
        )
        verify_pairing(
            {
                "metadata": {**metadata, "axes": {str(cell["id"]): [0]}, "error_rates": [cell["error_percent"]]},
                "rows": [{**row, "axis": cell["id"], "axis_value": 0} for row in selected],
                "populations": document["populations"],
            }
        )


def main(argv: list[str] | None = None, *, workspace: FixtureWorkspace | None = None) -> int:
    """
    Sweep structural and failure-placement axes through the production comparison engine.

    Args:
        argv (list[str] | None): Explicit CLI options.
        workspace (FixtureWorkspace | None): Owner of the reusable chart directory.

    Returns:
        int: Zero for complete measurements, one for harness failure or 130 for interruption.
    """
    from hypothesis_helm.benchmarking.reporting.response_surface import plot

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("benchmarks/runs/response-surface"))
    parser.add_argument("--input-complexity", type=int, default=10)
    parser.add_argument("--planes", nargs="+", choices=("structure", "failures"), default=["structure", "failures"])
    parser.add_argument("--depths", nargs="+", type=int, default=[0, 2, 5])
    parser.add_argument("--redundant-inputs", nargs="+", type=int, default=[0, 4, 8])
    parser.add_argument("--error-rates", nargs="+", type=float, default=list(RATES))
    parser.add_argument("--clustering", nargs="+", type=float, default=[step / 10 for step in range(11)])
    parser.add_argument("--fixed-error-rate", type=float, default=5)
    parser.add_argument("--fixed-depth", type=int, default=2)
    parser.add_argument("--fixed-redundant-inputs", type=int, default=6)
    parser.add_argument("--methods", nargs="+", choices=METHODS, default=["default", "filter", "filter-adaptive"])
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--error-seed", type=int, default=1729)
    parser.add_argument("--time-limit", type=parse_time_limit, default=540)
    parser.add_argument("--helm", default="helm")
    parser.add_argument("--plot-only", action="store_true")
    args = parser.parse_args(argv)
    if args.plot_only:
        plot(args.output, mapping(json.loads((args.output / "results.json").read_text())))
        return 0
    if not 2 <= args.input_complexity <= 12 or args.repeats < 1 or not 0 < args.time_limit <= 540:
        parser.error("require 2..12 fields, positive repeats and an execution ceiling in (0, 9m]")
    if any(
        len(values) != len(set(values))
        for values in (args.planes, args.methods, args.depths, args.redundant_inputs, args.error_rates, args.clustering)
    ):
        parser.error("axis values, planes and methods must be unique")
    if not all(0 <= depth <= args.input_complexity for depth in [*args.depths, args.fixed_depth]):
        parser.error("condition depths must fit the fixed field count")
    if not all(0 <= unused < args.input_complexity for unused in [*args.redundant_inputs, args.fixed_redundant_inputs]):
        parser.error("redundancy must leave a live primary-output field")
    if not all(math.isfinite(rate) and 0 <= rate <= 100 for rate in [*args.error_rates, args.fixed_error_rate]):
        parser.error("error percentages must be finite and in 0..100")
    if not all(math.isfinite(value) and 0 <= value <= 1 for value in args.clustering):
        parser.error("clustering must be finite and in 0..1")
    if (args.output / "results.json").exists():
        parser.error("choose a new output directory or use --plot-only")
    if workspace is None:
        with FixtureWorkspace() as owned:
            return main(argv, workspace=owned)
    cells: list[dict[str, object]] = []
    if "structure" in args.planes:
        for depth, unused in itertools.product(args.depths, args.redundant_inputs):
            cells.append(
                {
                    "id": f"structure-{depth}-{unused}",
                    "plane": "structure",
                    "x": unused,
                    "y": depth,
                    "condition_depth": depth,
                    "quantile_unused_inputs": unused,
                    "error_percent": args.fixed_error_rate,
                    "clustering": 0.0,
                }
            )
    if "failures" in args.planes:
        for rate, clustering in itertools.product(args.error_rates, args.clustering):
            cells.append(
                {
                    "id": f"failures-{rate:g}-{clustering:g}",
                    "plane": "failures",
                    "x": clustering,
                    "y": rate,
                    "condition_depth": args.fixed_depth,
                    "quantile_unused_inputs": args.fixed_redundant_inputs,
                    "error_percent": rate,
                    "clustering": clustering,
                }
            )
    rows: list[dict[str, object]] = []
    populations: dict[str, object] = {}
    metadata: dict[str, object] = {
        "status": "running",
        "code_sha256": code_digest(),
        "profiling": profile_settings(),
        "helm": Processes().run([args.helm, "version", "--short"], capture_output=True, check=True, timeout=30).stdout.strip(),
        "input_fields": args.input_complexity,
        "cells": cells,
        "methods": args.methods,
        "repeats": args.repeats,
        "seed": args.seed,
        "error_seed": args.error_seed,
        "time_limit_seconds": args.time_limit,
        "time_limit_scope": "execution per method; planning and analysis measured separately",
        "workers": 1,
        "reference": REFERENCE,
        "design": "Full discrete two-factor grids; other controls held constant within each plane; no fitted surface.",
        "cache": "Fresh per-method render hashes and compiler representatives; operating-system caches may remain warm.",
        "error_contract": "Known erroneous input assignments checked by an input-aware assertion; not counts of distinct chart defects.",
    }
    document: dict[str, object] = {"metadata": metadata, "rows": rows, "populations": populations}
    args.output.mkdir(parents=True, exist_ok=True)
    save(args.output, document)
    tasks = list(itertools.product(range(len(cells)), range(args.repeats)))
    random.Random(args.seed).shuffle(tasks)
    failed = False
    try:
        with BenchmarkProgress("Response surface") as display:
            display.total = len(tasks) * len(args.methods)
            display.progress.update(display.task, total=display.total)
            for index, repeat in tasks:
                cell = cells[index]
                logical = args.output / "charts" / str(cell["id"])
                generate(
                    logical,
                    input_complexity=args.input_complexity,
                    output_bins=2 ** (args.input_complexity - int(str(cell["quantile_unused_inputs"]))),
                    readable_inputs=False,
                    workspace=workspace,
                )
                spec = configure_surface(logical, int(str(cell["condition_depth"])), workspace=workspace)
                chart = Chart.load(chart_path(logical, workspace=workspace))
                reference = reference_space(chart, spec, 2**args.input_complexity)
                population = ErrorPopulation.build(
                    tuple(sorted(chart.defaults)),
                    float(str(cell["error_percent"])),
                    float(str(cell["clustering"])),
                    args.error_seed + repeat,
                )
                key = hashlib.sha256(configuration_key({"failed": sorted(population.failed)}).encode()).hexdigest()
                populations[key] = sorted(population.failed)
                methods = list(args.methods)
                random.Random(f"{args.seed}:{cell['id']}:{repeat}").shuffle(methods)
                for order, method in enumerate(methods):
                    row = measure(
                        chart,
                        spec,
                        method,
                        level=2,
                        seed=args.seed + repeat,
                        limit=2**args.input_complexity,
                        seconds=args.time_limit,
                        helm=args.helm,
                        reference=reference,
                        strength=2,
                        failure_oracle=partial(population.erroneous, spec=spec),
                    )
                    for field in (
                        "oracle_counts",
                        "observed_counts",
                        "selection_evidence",
                        "topology",
                        "distribution",
                        "failure_values",
                        "hashes",
                        "defects_found",
                    ):
                        row.pop(field, None)
                    found = int(str(row["erroneous_inputs_evaluated"]))
                    count = len(population.failed)
                    row.update(
                        {
                            **cell,
                            "case": cell["id"],
                            "repeat": repeat,
                            "order": order,
                            "error_seed": args.error_seed + repeat,
                            "error_count": count,
                            "actual_error_percent": 100 * count / len(reference[0]),
                            "errors_detected": found,
                            "errors_missed": count - found,
                            "error_recall": found / count if count else None,
                            "neighbor_error_fraction": population.neighbor_fraction,
                            "population_sha256": key,
                        }
                    )
                    rows.append(row)
                    save(args.output, document)
                    display.completed = len(rows)
                    display.progress.update(display.task, completed=len(rows))
                    print(
                        f"{len(rows)}/{display.total} {cell['id']} repeat={repeat + 1} {method}: "
                        f"{row['total_seconds']:.2f}s, {count - found}/{count} erroneous inputs missed, {row['status']}",
                        flush=True,
                    )
                    if row["status"] == "interrupted":
                        raise KeyboardInterrupt
                    failed |= row["status"] not in {"passed", "time-limit"}
    except KeyboardInterrupt:
        metadata["status"] = "interrupted"
        save(args.output, document)
        if rows:
            plot(args.output, document)
        return 130
    metadata["status"] = "failed" if failed else "complete"
    save(args.output, document)
    if not failed:
        verify(document)
    plot(args.output, document)
    return int(failed)
