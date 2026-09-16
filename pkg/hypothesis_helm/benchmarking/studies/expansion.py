"""
Compare failure expansion policies using fresh Helm populations and rerendered additional checks.
"""

import argparse
import json
import shutil
import time
from pathlib import Path

from hypothesis_helm.benchmarking.analysis.selection import decision
from hypothesis_helm.benchmarking.charts.fixture import FixtureWorkspace, chart_path
from hypothesis_helm.benchmarking.charts.structures import STRUCTURES
from hypothesis_helm.benchmarking.execution.profiling import profile_settings
from hypothesis_helm.benchmarking.execution.provenance import code_digest
from hypothesis_helm.benchmarking.reporting.progress import BenchmarkProgress
from hypothesis_helm.benchmarking.studies.matrix import bundle_key
from hypothesis_helm.benchmarking.studies.pca import run_case
from hypothesis_helm.charts.model import Chart
from hypothesis_helm.charts.rendering import render
from hypothesis_helm.compiler.passes.expansion import FailureExpansion
from hypothesis_helm.execution.processes import Processes
from hypothesis_helm.reporting.budget import TimeLimitReached, execution_timer, parse_time_limit
from hypothesis_helm.schemas.contracts import mapping, number, sequence


def erroneous(outcome: dict[str, object]) -> bool:
    """
    Read the observed error projection without consulting fault-placement metadata.

    Args:
        outcome (dict[str, object]): Canonical manifest bundle from an actual reference render.

    Returns:
        bool: Whether the rendered error projection violates the expected-status assertion.
    """
    for encoded in sequence(outcome["resources"]):
        resource = mapping(json.loads(str(encoded)))
        if mapping(resource.get("metadata", {})).get("name") == "benchmark-error":
            return mapping(resource["data"])["status"] != "expected"
    raise ValueError("reference outcome has no benchmark error projection")


def compare(chart: Chart, reference: dict[str, object], helm: str, seconds: float) -> list[dict[str, object]]:
    """
    Replay initial observations and execute added cases for each enabled policy.

    Args:
        chart (Chart): Fresh fixture including the injected faults.
        reference (dict[str, object]): Complete independently verified Helm population.
        helm (str): Fixed Helm binary for expansion checks.
        seconds (float): Remaining category execution budget after reference rendering.

    Returns:
        list[dict[str, object]]: Paired coverage, input counts and additional-render evidence.
    """
    values = [mapping(value) for value in sequence(reference["values"])]
    outcomes = [mapping(value) for value in sequence(reference["outcomes"])]
    identities = [int(number(value)) for value in sequence(reference["outcome_indices"])]
    failed_outputs = {index for index, outcome in enumerate(outcomes) if erroneous(outcome)}
    failures = {index for index, identity in enumerate(identities) if identity in failed_outputs}
    candidates = [int(number(index)) for index in sequence(reference.get("candidate_indices", list(range(len(values)))))]
    candidate_positions = {index: position for position, index in enumerate(candidates)}
    candidate_values = [values[index] for index in candidates]
    rows: list[dict[str, object]] = []
    spent = 0.0
    for strategy, raw_indices in mapping(reference.get("initial_selected_indices", reference["selected_indices"])).items():
        initial = [int(number(index)) for index in sequence(raw_indices)]
        for enabled in (False, True):
            scheduler = FailureExpansion.build(
                chart.path,
                chart.defaults,
                candidate_values,
                candidate_values,
                [candidate_positions[index] for index in initial],
            )
            queue = list(initial)
            checked: list[int] = []
            found: set[int] = set()
            extra = 0
            elapsed = 0.0
            status = "complete"
            with BenchmarkProgress(f"{strategy}, expansion={enabled}: checks") as display:
                for position, index in enumerate(display.track(queue)):
                    failed = identities[index] in failed_outputs
                    if position >= len(initial):
                        remaining = seconds - spent
                        if remaining <= 0:
                            status = "time-limit"
                            break
                        started = time.perf_counter()
                        try:
                            with execution_timer(remaining):
                                received = render(
                                    chart,
                                    values[index],
                                    helm=helm,
                                    release="matrix",
                                    timeout=min(30, remaining),
                                )
                                actual = mapping(json.loads(bundle_key(received)))
                                if actual != outcomes[identities[index]]:
                                    raise AssertionError("expanded render differs from verified reference")
                                failed = erroneous(actual)
                        except TimeLimitReached:
                            status = "time-limit"
                            break
                        finally:
                            duration = time.perf_counter() - started
                            spent += duration
                            elapsed += duration
                        extra += 1
                    checked.append(index)
                    if failed:
                        found.add(index)
                        if enabled:
                            queue.extend(candidates[added] for added in scheduler.failed(candidate_positions[index]))
            rows.append(
                {
                    "structure": reference["structure"],
                    "strategy": strategy,
                    "expand_failures": enabled,
                    **decision(mapping(mapping(reference.get("topology", {})).get(strategy, {}))),
                    "status": status,
                    "initial_checks": len(initial),
                    "checked_inputs": len(checked),
                    "additional_scheduled": len(scheduler.added),
                    "additional_executed": extra,
                    "additional_render_seconds": elapsed,
                    "remaining": len(queue) - len(checked),
                    "erroneous_inputs_found": len(found),
                    "erroneous_inputs_total": len(failures),
                    "erroneous_input_recall": len(found) / len(failures) if failures else None,
                    "erroneous_outputs_found": len({identities[index] for index in found}),
                    "erroneous_outputs_total": len(failed_outputs),
                    "erroneous_output_coverage": len({identities[index] for index in found}) / len(failed_outputs)
                    if failed_outputs
                    else None,
                    "all_output_coverage": len({identities[index] for index in checked}) / len(outcomes),
                    "checked_indices": checked,
                    "additional_indices": [candidates[index] for index in scheduler.added],
                    "unclassified_inputs": len(candidates) - len(scheduler.membership),
                    "inferred_failures": 0,
                }
            )
    return rows


def main(argv: list[str] | None = None, *, workspace: FixtureWorkspace | None = None) -> int:
    """
    Produce a paired six-category matrix under a shared nine-minute execution ceiling per category.

    Args:
        argv (list[str] | None): Explicit command arguments or the process command line.
        workspace (FixtureWorkspace | None): Explicit owner of the invocation's reusable chart.

    Returns:
        int: Zero for a complete comparison; one for a censored reference or expansion.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".cache/benchmarks/expansion"))
    parser.add_argument("--input-complexity", type=int, default=10)
    parser.add_argument("--error-percent", type=float, default=5)
    parser.add_argument("--error-seed", type=int, default=1729)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--trim-level", type=int, default=2)
    parser.add_argument("--time-limit", type=parse_time_limit, default=540.0)
    parser.add_argument("--helm", default="helm")
    parser.add_argument("--plot-only", action="store_true")
    args = parser.parse_args(argv)
    from hypothesis_helm.benchmarking.reporting.expansion import plot

    if args.plot_only:
        plot(args.output, mapping(json.loads((args.output / "results.json").read_text())))
        return 0
    if not (6 <= args.input_complexity <= 12 and 0 <= args.error_percent <= 100 and args.trim_level >= 0 and 0 < args.time_limit <= 540):
        parser.error("require 6..12 inputs, 0..100% errors, nonnegative trim and a ceiling <=9m")
    helm = shutil.which(args.helm)
    if not helm:
        parser.error("Helm is required")
    if (args.output / "results.json").exists():
        parser.error("output already contains results; choose another directory")
    args.output.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    references: list[dict[str, object]] = []
    document: dict[str, object] = {
        "metadata": {
            "profiling": profile_settings(),
            "helm": Processes().run([helm, "version", "--short"], capture_output=True, check=True, timeout=30).stdout.strip(),
            "code_sha256": code_digest(),
            "input_complexity": args.input_complexity,
            "error_percent": args.error_percent,
            "error_seed": args.error_seed,
            "seed": args.seed,
            "trim_level": args.trim_level,
            "time_limit_seconds": args.time_limit,
            "method": (
                "fresh full Helm population per category; paired policies replay "
                "initial observations; added checks rerendered per enabled policy"
            ),
            "budget": (
                "reference rendering plus all added renders share the category ceiling; planning, partitioning and plotting excluded"
            ),
            "interpretation": ("policy check counts are not independent full-run timing measurements; no inferred failures"),
        },
        "rows": rows,
        "references": references,
    }
    for structure in STRUCTURES:
        print(f"{structure}: fresh reference and paired failure expansion", flush=True)
        reference = run_case(
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
        references.append(reference)
        if reference["status"] == "complete":
            rows.extend(
                compare(
                    Chart.load(chart_path(args.output / "charts" / structure, workspace=workspace)),
                    reference,
                    helm,
                    args.time_limit - number(reference["execution_seconds"]),
                )
            )
        temporary = args.output / "results.tmp"
        temporary.write_text(json.dumps(document, indent=2) + "\n")
        temporary.replace(args.output / "results.json")
        if reference["status"] != "complete" or any(row["status"] != "complete" for row in rows):
            print("Execution ceiling reached; saved partial counts and remaining work.", flush=True)
            return 1
        added = sum(int(number(row["additional_executed"])) for row in rows if row["structure"] == structure)
        print(
            f"  complete; {added} added renders",
            flush=True,
        )
    plot(args.output, document)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
