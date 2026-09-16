"""
Compare real Helm execution and sampling across independently specified structural cases.
"""

import argparse
import hashlib
import itertools
import json
import logging
import platform
import random
import shutil
import subprocess
import time
from collections import Counter
from collections.abc import Callable, Sequence
from pathlib import Path

from jsonschema import validators

from hypothesis_helm.benchmarking.analysis.selection import PRESETS, decision
from hypothesis_helm.benchmarking.analysis.selection import select as select_preset
from hypothesis_helm.benchmarking.charts.fixture import FixtureWorkspace, chart_path
from hypothesis_helm.benchmarking.charts.generator import generate
from hypothesis_helm.benchmarking.charts.structures import STRUCTURES, expected_manifests, valid_assignment
from hypothesis_helm.benchmarking.charts.workload import source_digest
from hypothesis_helm.benchmarking.execution.profiling import profile_settings
from hypothesis_helm.benchmarking.execution.provenance import code_digest
from hypothesis_helm.benchmarking.reporting.progress import BenchmarkProgress
from hypothesis_helm.benchmarking.studies.sparsity import quality
from hypothesis_helm.charts.model import Chart
from hypothesis_helm.charts.rendering import render
from hypothesis_helm.compiler.passes.expansion import FailureExpansion
from hypothesis_helm.compiler.passes.pruning import Pruner
from hypothesis_helm.compiler.passes.topology import trim_topology
from hypothesis_helm.execution.processes import Processes
from hypothesis_helm.execution.render_hashes import RenderHashes
from hypothesis_helm.execution.sampling import Sampling
from hypothesis_helm.reporting.budget import TimeLimitReached, execution_timer, parse_time_limit
from hypothesis_helm.schemas.combinations import plan_interactions, trim_values
from hypothesis_helm.schemas.contracts import configuration_key, json_value, mapping, sequence
from hypothesis_helm.schemas.model import ValuesModel

STRATEGIES = ("default", "exact-equivalence", "random", "topology", "combined", *PRESETS)


def bundle_key(resources: list[dict[str, object]]) -> str:
    """
    Identify a complete manifest multiset, preserving resource content and duplicates.

    Args:
        resources (list[dict[str, object]]): Rendered or independently expected resources.

    Returns:
        str: Exact normalized resource multiset key.
    """
    return configuration_key({"resources": sorted(configuration_key(item) for item in resources)})


def reference_space(chart: Chart, spec: dict[str, object], limit: int) -> tuple[set[str], Counter[str]]:
    """
    Enumerate the fixture's independent valid input and output truth before sampling.

    Args:
        chart (Chart): Loaded structural fixture.
        spec (dict[str, object]): Generator metadata.
        limit (int): Maximum raw domain size to enumerate.

    Returns:
        tuple[set[str], Counter[str]]: Exact valid input identities and output multiplicities.
    """
    properties = mapping(chart.schema["properties"])
    paths = list(properties)
    domains = [sequence(mapping(properties[path]).get("enum", [False, True])) for path in paths]
    size = 1
    for domain in domains:
        assert isinstance(domain, list)
        size *= len(domain)
    if size > limit:
        raise ValueError("fixture domain exceeds --max-cases; reduce input complexity")
    identities: set[str] = set()
    outcomes: Counter[str] = Counter()
    validator = validators.validator_for(chart.schema)(chart.schema)
    for items in itertools.product(*domains):
        values = dict(zip(paths, items, strict=True))
        valid = valid_assignment(values, spec)
        if validator.is_valid(json_value(values)) != valid:
            raise AssertionError("schema and independent input-constraint oracle disagree")
        if valid:
            identities.add(configuration_key(values))
            outcomes[bundle_key(expected_manifests(values, spec))] += 1
    return identities, outcomes


def measure(
    chart: Chart,
    spec: dict[str, object],
    strategy: str,
    *,
    level: int,
    seed: int,
    limit: int,
    seconds: float,
    helm: str,
    reference: tuple[set[str], Counter[str]],
    strength: int | None = None,
    failure_oracle: Callable[[dict[str, object], list[dict[str, object]]], bool] | None = None,
    manifest_oracle: Callable[[dict[str, object], dict[str, object]], list[dict[str, object]]] = expected_manifests,
) -> dict[str, object]:
    """
    Plan afresh, apply production selectors, and validate every completed output against its oracle.

    Args:
        chart (Chart): Structural fixture.
        spec (dict[str, object]): Independent oracle parameters.
        strategy (str): Execution strategy to measure.
        level (int): Quarter-retention depth for each enabled trim control.
        seed (int): Common reproducible sampling seed.
        limit (int): Finite planning bound.
        seconds (float): Execution deadline excluding planning and analysis.
        helm (str): Pinned Helm binary.
        reference (tuple[set[str], Counter[str]]): Exact input and output truth.
        strength (int | None): Fixed interaction strength; otherwise use the field count.
        failure_oracle (Callable[[dict[str, object], list[dict[str, object]]], bool] | None): Optional input-aware property assertion.
        manifest_oracle (Callable[[dict[str, object], dict[str, object]], list[dict[str, object]]]): Independent expected manifest builder.

    Returns:
        dict[str, object]: Measured row, including censored work and correctness evidence.
    """
    if strategy not in (*STRATEGIES, "sample-random"):
        raise ValueError(f"unknown matrix strategy: {strategy}")
    started = time.perf_counter()
    model = ValuesModel.from_schema(chart.schema)
    selection_strength = 2 if strength is None else strength
    strength = len(mapping(chart.schema["properties"])) if strength is None else strength
    plan = plan_interactions(model, strength, max_cases=limit, max_candidates=limit)
    baseline_key = configuration_key(chart.defaults)
    planned = {configuration_key(value): value for value in plan.values}
    planned[baseline_key] = chart.defaults
    if set(planned) != reference[0]:
        raise AssertionError("finite planner disagrees with independent valid-domain oracle")
    candidates = [value for key, value in planned.items() if key != baseline_key]
    if failure_oracle is not None:
        random.Random(seed).shuffle(candidates)
    all_candidates = [chart.defaults, *candidates]
    positions = {configuration_key(value): index for index, value in enumerate(all_candidates)}
    planning_seconds = time.perf_counter() - started
    analysis_started = time.perf_counter()
    topology: dict[str, object] = {}
    evidence: dict[str, object] = {}
    selected: Sequence[dict[str, object]] = candidates
    if strategy in PRESETS:
        selected, evidence = select_preset(chart, candidates, strategy, seed, strength=selection_strength)
        topology = mapping(evidence["topology"])
    elif strategy in {"topology", "combined"}:
        selected, topology = trim_topology(
            chart.path,
            chart.defaults,
            candidates,
            candidates,
            level,
            seed,
            random_steps=level if strategy == "combined" else 0,
        )
    elif strategy == "random":
        selected = trim_values(candidates, level, seed)
    elif strategy == "sample-random":
        selected, evidence = Sampling(70).select(candidates, configuration_key, seed)
    candidates = [chart.defaults, *selected]
    initial_selected = len(candidates)
    expansion = (
        FailureExpansion.build(
            chart.path, chart.defaults, all_candidates, all_candidates, [positions[configuration_key(value)] for value in candidates]
        )
        if strategy in PRESETS
        else None
    )
    compiler = Pruner(chart.path, chart.defaults, model) if strategy == "exact-equivalence" else None
    analysis_seconds = time.perf_counter() - analysis_started
    hashes = RenderHashes(scope="matrix-run-local")
    ledger: list[tuple[str, bool]] = []
    attempted = invocations = 0
    found_defects: set[str] = set()
    erroneous_inputs = rendered_erroneous_inputs = 0
    error = None
    status = "passed"
    context = configuration_key({"helm": helm, "release": "matrix", "namespace": "default"})
    started = time.perf_counter()
    current: dict[str, object] | None = None
    try:
        initial_remaining = seconds - (time.perf_counter() - started)
        if initial_remaining <= 0:
            raise TimeLimitReached()
        with execution_timer(initial_remaining):
            with BenchmarkProgress(f"{chart.path.name} / {strategy}: checks") as display:
                for current in display.track(candidates):
                    remaining = seconds - (time.perf_counter() - started)
                    if remaining <= 0:
                        raise TimeLimitReached()
                    attempted += 1
                    witness = compiler.candidate(current, current, context) if compiler else None
                    resources = compiler.lookup(witness, attempted) if compiler else None
                    reused = resources is not None
                    if resources is None:
                        invocations += 1
                        resources = render(
                            chart,
                            current,
                            helm=helm,
                            release="matrix",
                            timeout=min(30, remaining),
                            hashes=hashes,
                        )
                    actual = bundle_key(resources)
                    if actual != bundle_key(manifest_oracle(current, spec)):
                        raise AssertionError("Helm output differs from the independent manifest oracle")
                    if compiler:
                        compiler.remember(witness, attempted, resources)
                    defects = {
                        str(mapping(resource.get("metadata", {})).get("name", ""))
                        for resource in resources
                        if str(mapping(resource.get("metadata", {})).get("name", "")).startswith("defect-")
                        and mapping(resource.get("data", {})).get("status") == "incorrect"
                    }
                    if failure_oracle is not None and failure_oracle(current, resources):
                        defects.add("input-aware-property")
                    found_defects.update(defects)
                    if defects and expansion is not None:
                        candidates.extend(all_candidates[index] for index in expansion.failed(positions[configuration_key(current)]))
                    erroneous_inputs += bool(defects)
                    rendered_erroneous_inputs += bool(defects) and not reused
                    ledger.append((actual, reused))
    except TimeLimitReached:
        status = "time-limit"
    except KeyboardInterrupt:
        if failure_oracle is None:
            raise
        status = "interrupted"
    except Exception as exc:
        if isinstance(exc.__cause__, subprocess.TimeoutExpired) and time.perf_counter() - started >= seconds:
            status = "time-limit"
        else:
            status, error = "failed", f"{type(exc).__name__}: {exc}"
    execution_seconds = time.perf_counter() - started
    received = Counter(actual for actual, _ in ledger)
    completed = len(ledger)
    skipped = sum(reused for _, reused in ledger)
    distribution = quality(dict(received), dict(reference[1]), ordered=False) if received else None
    return {
        "structure": mapping(spec["structure"])["name"],
        "strategy": strategy,
        "trim_level": level,
        "trim_random": level if strategy in {"random", "combined"} else 0,
        "trim_topology": 2 if strategy in PRESETS else level if strategy in {"topology", "combined"} else 0,
        "initial_selected": initial_selected,
        "expand_failures": strategy in PRESETS,
        "additional_scheduled": len(expansion.added) if expansion else 0,
        "additional_executed": max(0, completed - initial_selected),
        "selection_evidence": evidence,
        **decision(evidence),
        "seed": seed,
        "status": status,
        "error": error,
        "failure_values": current if error else None,
        "time_limit_seconds": seconds,
        "valid_domain": len(reference[0]),
        "possible_outcomes": len(reference[1]),
        "selected": len(candidates),
        "omitted": len(reference[0]) - len(candidates),
        "attempted": attempted,
        "completed": completed,
        "remaining": len(candidates) - completed,
        "render_invocations": invocations,
        "proved_equivalent": skipped,
        "defects_found": sorted(found_defects),
        "erroneous_inputs_evaluated": erroneous_inputs,
        "erroneous_inputs_rendered": rendered_erroneous_inputs,
        "observed_outcomes": len(received),
        "distribution": distribution,
        "planning_seconds": planning_seconds,
        "analysis_seconds": analysis_seconds,
        "execution_seconds": execution_seconds,
        "total_seconds": planning_seconds + analysis_seconds + execution_seconds,
        "topology": topology,
        "compiler_fallback": compiler.disabled if compiler else None,
        "selected_sha256": hashlib.sha256(configuration_key({"values": candidates}).encode()).hexdigest(),
        "oracle_counts": dict(reference[1]),
        "observed_counts": dict(received),
        "chart_sha256": source_digest(chart.path),
        "hashes": hashes.snapshot(),
    }


def main(argv: list[str] | None = None, *, workspace: FixtureWorkspace | None = None) -> int:
    """
    Run every strategy against every structural case with a common nine-minute ceiling.

    Args:
        argv (list[str] | None): Explicit command arguments or the process command line.
        workspace (FixtureWorkspace | None): Explicit owner of the invocation's reusable chart.

    Returns:
        int: Zero for completed or deadline-censored measurements; one for incorrect renders.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".cache/benchmarks/matrix"))
    parser.add_argument("--input-complexity", type=int, default=10)
    parser.add_argument("--max-cases", type=int, default=4096)
    parser.add_argument("--trim-level", type=int, default=2)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--time-limit", type=parse_time_limit, default=540.0)
    parser.add_argument("--helm", default="helm")
    parser.add_argument("--plot-only", action="store_true")
    args = parser.parse_args(argv)
    from hypothesis_helm.benchmarking.reporting.matrix import plot

    if args.plot_only:
        plot(args.output, mapping(json.loads((args.output / "results.json").read_text())))
        return 0
    if not 0 < args.time_limit <= 540 or args.trim_level < 1 or not 6 <= args.input_complexity <= 12:
        parser.error("require time limit <=9m, positive trim level, and 6..12 inputs")
    helm = shutil.which(args.helm)
    if helm is None:
        parser.error("Helm is required")
    if (args.output / "results.json").exists():
        parser.error("output already contains measurements; use another directory")
    args.output.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.WARNING)
    rows: list[dict[str, object]] = []
    document: dict[str, object] = {
        "metadata": {
            "profiling": profile_settings(),
            "helm": Processes().run([helm, "version", "--short"], capture_output=True, check=True, timeout=30).stdout.strip(),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "code_sha256": code_digest(),
            "time_limit_seconds": args.time_limit,
            "input_complexity": args.input_complexity,
            "trim_level": args.trim_level,
            "seed": args.seed,
            "repeats": 1,
            "method": "complete finite-domain oracle; fresh sequential runs; production selectors and pruner",
            "timing": "execution ceiling excludes planning/analysis; all three costs reported",
            "strategies": list(STRATEGIES),
            "structures": list(STRUCTURES),
        },
        "rows": rows,
    }
    for structure in STRUCTURES:
        path = args.output / "charts" / structure
        spec = generate(path, input_complexity=args.input_complexity, output_bins=4, structure=structure, workspace=workspace)
        chart = Chart.load(chart_path(path, workspace=workspace))
        truth = reference_space(chart, spec, args.max_cases)
        for strategy in STRATEGIES:
            print(
                f"{structure} / {strategy}: {len(truth[0])} valid inputs, {args.time_limit:g}s ceiling",
                flush=True,
            )
            row = measure(
                chart,
                spec,
                strategy,
                level=args.trim_level,
                seed=args.seed,
                limit=args.max_cases,
                seconds=args.time_limit,
                helm=helm,
                reference=truth,
            )
            rows.append(row)
            temporary = args.output / "results.tmp"
            temporary.write_text(json.dumps(document, indent=2) + "\n")
            temporary.replace(args.output / "results.json")
            print(
                f"  {row['status']}: {row['completed']}/{row['selected']} checks, "
                f"{row['observed_outcomes']}/{row['possible_outcomes']} outcomes; "
                f"{row['execution_seconds']:.2f}s execution",
                flush=True,
            )
            if row["status"] == "failed":
                return 1
    plot(args.output, document)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
