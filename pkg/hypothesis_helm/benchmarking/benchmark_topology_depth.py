"""
Sweep topology depth against fixed faulty populations and distributed structural fixtures.
"""

import argparse
import json
import shutil
import subprocess
import time
from pathlib import Path

from hypothesis_helm.benchmarking.benchmark_expansion import compare
from hypothesis_helm.benchmarking.benchmark_helm import code_digest
from hypothesis_helm.benchmarking.benchmark_pca import run_case
from hypothesis_helm.benchmarking.structures import STRUCTURES
from hypothesis_helm.charts.runner import Chart
from hypothesis_helm.compiler.topology import trim_topology
from hypothesis_helm.reporting.budget import parse_time_limit
from hypothesis_helm.schemas.contracts import configuration_key, mapping, number, sequence


def sweep(
    chart: Chart,
    reference: dict[str, object],
    depths: list[int],
    seed: int,
    helm: str,
    seconds: float,
) -> list[dict[str, object]]:
    """
    Vary only topology depth, replay reference checks and physically execute expansion additions.

    Args:
        chart (Chart): Fixed fixture with faults present before filtering.
        reference (dict[str, object]): Independently verified complete reference population.
        depths (list[int]): Nonnegative topology trim depths.
        seed (int): Fixed selection seed.
        helm (str): Fixed Helm executable.
        seconds (float): Shared remaining execution budget after reference rendering.

    Returns:
        list[dict[str, object]]: Per-depth observed coverage and explicit execution accounting.
    """
    values = [mapping(value) for value in sequence(reference["values"])]
    positions = {configuration_key(value): index for index, value in enumerate(values)}
    rows = []
    spent = 0.0
    for depth in depths:
        started = time.perf_counter()
        selected, evidence = trim_topology(chart.path, chart.defaults, values[1:], values[1:], depth, seed, random_steps=0)
        selection_seconds = time.perf_counter() - started
        indices = [0, *(positions[configuration_key(value)] for value in selected)]
        paired = compare(
            chart,
            {**reference, "selected_indices": {"topology": indices}},
            helm,
            max(0, seconds - spent),
        )
        row = paired[1]
        spent += number(row["additional_render_seconds"])
        row.update(
            {
                "trim_topology": depth,
                "trim_random": 0,
                "selection_seconds": selection_seconds,
                "topology": evidence,
                "initial_erroneous_inputs_found": paired[0]["erroneous_inputs_found"],
            }
        )
        rows.append(row)
        if row["status"] != "complete":
            break
    return rows


def main() -> int:
    """
    Generate a matched depth sweep while preserving complete references and partial-run statistics.

    Returns:
        int: Zero for complete plots, one for execution-budget censoring.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("reports/benchmarks/topology-depth"))
    parser.add_argument("--depths", type=int, nargs="+", default=list(range(6)))
    parser.add_argument("--input-complexity", type=int, default=10)
    parser.add_argument("--error-percent", type=float, default=5)
    parser.add_argument("--error-seed", type=int, default=1729)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--topology-seed", type=int, default=2026)
    parser.add_argument("--topology-components", type=int, default=12)
    parser.add_argument("--time-limit", type=parse_time_limit, default=540.0)
    parser.add_argument("--helm", default="helm")
    parser.add_argument("--plot-only", action="store_true")
    args = parser.parse_args()
    from hypothesis_helm.benchmarking.depth_plots import plot

    if args.plot_only:
        plot(args.output, mapping(json.loads((args.output / "results.json").read_text())))
        return 0
    if not (
        7 <= args.input_complexity <= 12
        and 0 < args.error_percent <= 100
        and 0 < args.time_limit <= 540
        and 1 <= args.topology_components <= 1024
        and all(depth >= 0 for depth in args.depths)
        and len(set(args.depths)) == len(args.depths)
    ):
        parser.error("require 7..12 inputs, 0<errors<=100, ceiling<=9m, 1..1024 components and unique nonnegative depths")
    helm = shutil.which(args.helm)
    if not helm:
        parser.error("Helm is required")
    if (args.output / "results.json").exists():
        parser.error("results already exist; choose another output or --plot-only")
    args.output.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    references: list[dict[str, object]] = []
    document: dict[str, object] = {
        "metadata": {
            "helm": subprocess.check_output([helm, "version", "--short"], text=True).strip(),
            "code_sha256": code_digest(),
            "depths": args.depths,
            "input_complexity": args.input_complexity,
            "error_percent": args.error_percent,
            "error_seed": args.error_seed,
            "selection_seed": args.seed,
            "topology_seed": args.topology_seed,
            "topology_components": args.topology_components,
            "random_trim": 0,
            "expand_failures": True,
            "output_bins": 4,
            "time_limit_seconds": args.time_limit,
            "method": "fresh complete references; matched initial observation replay; additions physically rerendered per depth",
            "budget": "per fixture: reference plus all depth expansion renders; excludes planning and analysis",
        },
        "rows": rows,
        "references": references,
    }
    for structure in (*STRUCTURES, "mixed-uniform", "mixed-supported"):
        print(f"{structure}: fixed population, depth sweep {args.depths}", flush=True)
        reference = run_case(
            args.output,
            structure,
            args.input_complexity,
            args.error_percent,
            args.error_seed,
            args.seed,
            0,
            helm,
            args.time_limit,
            topology_components=args.topology_components if structure.startswith("mixed-") else 0,
            topology_weights={"dependencies": 1, "interactions": 1, "equivalence": 1} if structure == "mixed-supported" else None,
            topology_seed=args.topology_seed,
        )
        references.append(reference)
        if reference["status"] == "complete":
            rows.extend(
                sweep(
                    Chart.load(args.output / "charts" / structure),
                    reference,
                    args.depths,
                    args.seed,
                    helm,
                    args.time_limit - number(reference["execution_seconds"]),
                )
            )
        (args.output / "results.json").write_text(json.dumps(document, indent=2) + "\n")
        if reference["status"] != "complete" or any(row["status"] != "complete" for row in rows):
            return 1
        print("  complete", flush=True)
    plot(args.output, document)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
