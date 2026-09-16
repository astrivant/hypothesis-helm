"""
Measure error prevalence against condition depth, output redundancy, and failure clustering.
"""

import argparse
import csv
import hashlib
import itertools
import json
import math
import random
from fractions import Fraction
from functools import partial
from pathlib import Path

from hypothesis_helm.benchmarking.charts.error_surface import ErrorPopulation, configure_surface
from hypothesis_helm.benchmarking.charts.fixture import FixtureWorkspace, chart_path
from hypothesis_helm.benchmarking.charts.generator import generate
from hypothesis_helm.benchmarking.execution.profiling import profile_settings
from hypothesis_helm.benchmarking.execution.provenance import code_digest
from hypothesis_helm.benchmarking.reporting.progress import BenchmarkProgress
from hypothesis_helm.benchmarking.studies.matrix import STRATEGIES, measure, reference_space
from hypothesis_helm.charts.model import Chart
from hypothesis_helm.execution.processes import Processes
from hypothesis_helm.reporting.budget import parse_time_limit
from hypothesis_helm.schemas.contracts import configuration_key, mapping, sequence

METHODS = (*STRATEGIES, "sample-random")
RATES = (0, 1, 5, *range(10, 101, 10))
AXES = ("depth", "redundancy", "clustering")
METRICS = ("total_seconds", "render_invocations", "error_recall", "additional_executed")


def output_size(value: str) -> tuple[int, int]:
    """
    Parse measured clustering columns and error-rate rows.

    Args:
        value (str): Grid dimensions written as columns x rows.

    Returns:
        tuple[int, int]: Two dimensions, each at least two to include both endpoints.
    """
    try:
        columns, rows = (int(part) for part in value.lower().split("x"))
        if columns < 2 or rows < 2:
            raise ValueError
    except ValueError as error:
        raise argparse.ArgumentTypeError("use COLUMNSxROWS, with both dimensions at least 2 (for example 11x13)") from error
    return columns, rows


def grid_values(size: tuple[int, int]) -> tuple[list[float], list[float]]:
    """
    Generate endpoint-inclusive factor settings for the requested measurement grid.

    Args:
        size (tuple[int, int]): Validated clustering columns and error-rate rows.

    Returns:
        tuple[list[float], list[float]]: Clustering settings and error percentages;
            thirteen rows retain the established rare-error settings.
    """
    columns, rows = size
    return [index / (columns - 1) for index in range(columns)], (
        [float(rate) for rate in RATES] if rows == len(RATES) else [100 * index / (rows - 1) for index in range(rows)]
    )


def save(output: Path, document: dict[str, object]) -> None:
    """
    Checkpoint paired observations atomically before starting another measurement.

    Args:
        output (Path): New study output directory.
        document (dict[str, object]): Metadata, oracle populations, and completed rows.

    Returns:
        None: JSON preserves full evidence; CSV provides scalar measurement columns.
    """
    temporary = output / "results.tmp"
    temporary.write_text(json.dumps(document, indent=2, allow_nan=False) + "\n")
    temporary.replace(output / "results.json")
    rows = sequence(document["rows"])
    if rows:
        with (output / "results.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(mapping(rows[0])), lineterminator="\n")
            writer.writeheader()
            writer.writerows(mapping(row) for row in rows)


def verify(document: dict[str, object]) -> None:
    """
    Reject incomplete pairing, inconsistent denominators, or changed charts within a sweep.

    Args:
        document (dict[str, object]): Completed study ledger submitted for publication.

    Returns:
        None: Every requested measurement appears once and its statistics reconcile.
    """
    metadata = mapping(document["metadata"])
    rows = [mapping(row) for row in sequence(document["rows"])]
    populations = mapping(document["populations"])
    expected = {
        (axis, value, rate, repeat, method)
        for axis, settings in mapping(metadata["axes"]).items()
        for value, rate, repeat, method in itertools.product(
            sequence(settings), sequence(metadata["error_rates"]), range(int(str(metadata["repeats"]))), sequence(metadata["methods"])
        )
    }
    assert metadata["status"] == "complete"
    assert len(rows) == len(expected)
    assert {(row["axis"], row["axis_value"], row["error_percent"], row["repeat"], row["strategy"]) for row in rows} == expected
    hashes: dict[tuple[object, object], str] = {}
    pairs: dict[tuple[object, ...], str] = {}
    total = 2 ** int(str(metadata["input_fields"]))
    for row in rows:
        counts = {
            key: int(str(row[key]))
            for key in (
                "remaining",
                "selected",
                "completed",
                "additional_executed",
                "additional_scheduled",
                "render_invocations",
                "proved_equivalent",
                "initial_selected",
                "errors_detected",
                "error_count",
                "errors_missed",
            )
        }
        assert row["status"] in {"passed", "time-limit"}
        assert row["valid_domain"] == total
        assert counts["error_count"] == int(total * Fraction(str(row["error_percent"])) / 100)
        assert 0 <= counts["completed"] <= counts["selected"] <= total
        assert counts["remaining"] == counts["selected"] - counts["completed"]
        assert 0 <= counts["additional_executed"] <= counts["additional_scheduled"]
        if row["status"] == "passed":
            assert counts["remaining"] == 0
            assert counts["completed"] == counts["render_invocations"] + counts["proved_equivalent"]
            if row["strategy"] in {"default", "exact-equivalence"}:
                assert counts["completed"] == total and counts["errors_detected"] == counts["error_count"]
        assert counts["selected"] == counts["initial_selected"] + counts["additional_scheduled"]
        assert 0 <= counts["errors_detected"] <= counts["error_count"] <= total
        assert counts["errors_missed"] == counts["error_count"] - counts["errors_detected"]
        assert row["error_recall"] == (counts["errors_detected"] / counts["error_count"] if counts["error_count"] else None)
        assert row["actual_error_percent"] == 100 * counts["error_count"] / total
        assert all(math.isfinite(float(str(row[key]))) and float(str(row[key])) >= 0 for key in ("total_seconds", "execution_seconds"))
        assert math.isclose(
            float(str(row["total_seconds"])),
            sum(float(str(row[key])) for key in ("planning_seconds", "analysis_seconds", "execution_seconds")),
        )
        population = sequence(populations[str(row["population_sha256"])])
        assert len(population) == len(set(population)) == counts["error_count"]
        assert all(type(index) is int and 0 <= index < total for index in population)
        assert hashlib.sha256(configuration_key({"failed": population}).encode()).hexdigest() == row["population_sha256"]
        key = (row["axis"], row["axis_value"])
        assert hashes.setdefault(key, str(row["chart_sha256"])) == row["chart_sha256"]
        pair = (*key, row["error_percent"], row["repeat"])
        assert pairs.setdefault(pair, str(row["population_sha256"])) == row["population_sha256"]


def main(argv: list[str] | None = None, *, workspace: FixtureWorkspace | None = None) -> int:
    """
    Run controlled error-rate surfaces through the existing real-Helm comparison engine.

    Args:
        argv (list[str] | None): Explicit command-line arguments.
        workspace (FixtureWorkspace | None): Owner of this invocation's single reusable chart.

    Returns:
        int: Zero for complete paired runs, one for harness failures, or 130 after interruption.
    """
    from hypothesis_helm.benchmarking.reporting.error_surface import plot

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".cache/benchmarks/error-surface"))
    parser.add_argument("--input-complexity", type=int, default=8)
    parser.add_argument(
        "--output-size",
        type=output_size,
        default=(11, 13),
        metavar="COLUMNSxROWS",
        help="measured clustering columns x error-rate rows; default: 11x13; explicit axis lists override their dimension",
    )
    parser.add_argument("--error-rates", type=float, nargs="+", help="explicit error percentages; overrides the output-size row count")
    parser.add_argument("--axes", choices=AXES, nargs="+", default=list(AXES))
    parser.add_argument("--depths", type=int, nargs="+", default=list(range(6)))
    parser.add_argument("--redundant-inputs", type=int, nargs="+", help="unused Boolean fields; defaults to 0 through fields minus one")
    parser.add_argument("--clustering", type=float, nargs="+", help="explicit clustering settings; overrides the output-size column count")
    parser.add_argument("--methods", choices=METHODS, nargs="+", default=list(METHODS))
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--error-seed", type=int, default=1729)
    parser.add_argument("--permutations", type=int, default=2)
    parser.add_argument("--trim-level", type=int, default=2)
    parser.add_argument("--time-limit", type=parse_time_limit, default=540)
    parser.add_argument("--helm", default="helm")
    parser.add_argument("--plot-only", action="store_true")
    parser.add_argument("--symbolic-fit", action="store_true", help="also compare optional PySR fits with quadratics on held-out data")
    args = parser.parse_args(argv)
    if args.plot_only:
        plot(args.output, mapping(json.loads((args.output / "results.json").read_text())))
        if args.symbolic_fit:
            from hypothesis_helm.benchmarking.studies.symbolic_surface import main as symbolic_main

            return symbolic_main(["--input", str(args.output / "results.json")])
        return 0
    grid_clustering, grid_rates = grid_values(args.output_size)
    if args.clustering is None:
        args.clustering = grid_clustering
    if args.error_rates is None:
        args.error_rates = grid_rates
    if not 2 <= args.input_complexity <= 10 or not 1 <= args.permutations <= args.input_complexity:
        parser.error("require 2..10 fields and a positive interaction strength no larger than the field count")
    redundant = args.redundant_inputs if args.redundant_inputs is not None else list(range(args.input_complexity))
    if args.repeats < 1 or args.trim_level < 0 or not 0 < args.time_limit <= 540:
        parser.error("require positive repeats, nonnegative trim level, and an execution ceiling in (0, 9m]")
    if not all(math.isfinite(rate) and 0 <= rate <= 100 for rate in args.error_rates):
        parser.error("error rates must be finite percentages in 0..100")
    axes = {
        name: values
        for name, values in (("depth", args.depths), ("redundancy", redundant), ("clustering", args.clustering))
        if name in args.axes
    }
    if any(len(set(values)) != len(values) for values in [args.error_rates, args.axes, args.methods, *axes.values()]):
        parser.error("axis values, rates, and methods must be unique")
    if "depth" in axes and not all(0 <= depth <= args.input_complexity for depth in args.depths):
        parser.error("condition depths must fit the field count")
    if "redundancy" in axes and not all(0 <= count < args.input_complexity for count in redundant):
        parser.error("redundant inputs must leave at least one output-controlling field")
    if "clustering" in axes and not all(math.isfinite(value) and 0 <= value <= 1 for value in args.clustering):
        parser.error("clustering must be in 0..1")
    if (args.output / "results.json").exists():
        parser.error("choose a new output directory or use --plot-only")
    if workspace is None:
        with FixtureWorkspace() as owned:
            return main(argv, workspace=owned)
    args.output.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    populations: dict[str, object] = {}
    document: dict[str, object] = {
        "metadata": {
            "code_sha256": code_digest(),
            "helm": Processes().run([args.helm, "version", "--short"], capture_output=True, check=True, timeout=30).stdout.strip(),
            "profiling": profile_settings(),
            "status": "running",
            "input_fields": args.input_complexity,
            "axes": axes,
            "error_rates": args.error_rates,
            "repeats": args.repeats,
            "seed": args.seed,
            "error_seed": args.error_seed,
            "methods": args.methods,
            "permutations": args.permutations,
            "trim_level": args.trim_level,
            "time_limit_seconds": args.time_limit,
            "time_limit_scope": "execution per method; planning measured separately",
            "workers": 1,
            "assertion": "Rendered quantile must match the input-aware specification; selected inputs require a corrected value.",
            "cache": "Fresh per-method render hashes and compiler cache; no shared outcome cache; OS caches may remain warm.",
        },
        "rows": rows,
        "populations": populations,
    }
    metadata = mapping(document["metadata"])
    total_runs = sum(len(values) for values in axes.values()) * len(args.error_rates) * args.repeats * len(args.methods)
    failed = False
    try:
        with BenchmarkProgress("Error-rate surfaces") as display:
            display.total = total_runs
            display.progress.update(display.task, total=total_runs)
            for axis, settings in axes.items():
                for value in settings:
                    depth = int(value) if axis == "depth" else 0
                    unused = int(value) if axis == "redundancy" else args.input_complexity - 2
                    clustering = float(value) if axis == "clustering" else 0.0
                    logical = args.output / "charts" / f"{axis}-{value:g}"
                    generate(
                        logical,
                        input_complexity=args.input_complexity,
                        output_bins=2 ** (args.input_complexity - unused),
                        readable_inputs=False,
                        workspace=workspace,
                    )
                    spec = configure_surface(logical, depth, workspace=workspace)
                    chart = Chart.load(chart_path(logical, workspace=workspace))
                    reference = reference_space(chart, spec, 2**args.input_complexity)
                    for repeat in range(args.repeats):
                        for rate in args.error_rates:
                            population = ErrorPopulation.build(tuple(sorted(chart.defaults)), rate, clustering, args.error_seed + repeat)
                            population_key = hashlib.sha256(configuration_key({"failed": sorted(population.failed)}).encode()).hexdigest()
                            populations[population_key] = sorted(population.failed)
                            methods = list(args.methods)
                            random.Random(f"{args.seed}:{repeat}:{axis}:{value}:{rate}").shuffle(methods)
                            for order, method in enumerate(methods):
                                row = measure(
                                    chart,
                                    spec,
                                    method,
                                    level=args.trim_level,
                                    seed=args.seed + repeat,
                                    limit=2**args.input_complexity,
                                    seconds=args.time_limit,
                                    helm=args.helm,
                                    reference=reference,
                                    strength=args.permutations,
                                    failure_oracle=partial(population.erroneous, spec=spec),
                                )
                                for key in (
                                    "oracle_counts",
                                    "observed_counts",
                                    "selection_evidence",
                                    "topology",
                                    "distribution",
                                    "failure_values",
                                    "hashes",
                                    "defects_found",
                                ):
                                    row.pop(key, None)
                                count = len(population.failed)
                                found = int(str(row["erroneous_inputs_evaluated"]))
                                row.update(
                                    {
                                        "axis": axis,
                                        "axis_value": value,
                                        "condition_depth": depth,
                                        "quantile_unused_inputs": unused,
                                        "clustering": clustering,
                                        "repeat": repeat,
                                        "order": order,
                                        "error_percent": rate,
                                        "error_seed": args.error_seed + repeat,
                                        "error_count": count,
                                        "actual_error_percent": 100 * count / len(reference[0]),
                                        "errors_detected": found,
                                        "errors_missed": count - found,
                                        "error_recall": found / count if count else None,
                                        "neighbor_error_fraction": population.neighbor_fraction,
                                        "population_sha256": population_key,
                                    }
                                )
                                rows.append(row)
                                save(args.output, document)
                                display.completed = len(rows)
                                display.progress.update(display.task, completed=len(rows))
                                print(
                                    f"{len(rows)}/{total_runs} {axis}={value:g} errors={rate:g}% repeat={repeat + 1} {method}: "
                                    f"{row['total_seconds']:.3f}s, {found}/{count} erroneous inputs, "
                                    f"+{row['additional_executed']} expanded, {row['status']}",
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
    if args.symbolic_fit and not failed:
        from hypothesis_helm.benchmarking.studies.symbolic_surface import main as symbolic_main

        return symbolic_main(["--input", str(args.output / "results.json")])
    return int(failed)
