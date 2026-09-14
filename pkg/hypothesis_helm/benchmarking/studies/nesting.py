"""
Compare structural gate-depth distributions at fixed permutation interaction strength.
"""

import argparse
import json
import shutil
import time
from pathlib import Path

from hypothesis_helm.benchmarking.analysis.pca import project
from hypothesis_helm.benchmarking.charts.fixture import FixtureWorkspace, chart_path
from hypothesis_helm.benchmarking.execution.profiling import profile_settings
from hypothesis_helm.benchmarking.execution.provenance import code_digest
from hypothesis_helm.benchmarking.studies.expansion import compare
from hypothesis_helm.benchmarking.studies.pca import run_case, selections
from hypothesis_helm.charts.model import Chart
from hypothesis_helm.execution.processes import Processes
from hypothesis_helm.reporting.budget import parse_time_limit
from hypothesis_helm.schemas.combinations import plan_interactions
from hypothesis_helm.schemas.contracts import configuration_key, mapping, number, sequence
from hypothesis_helm.schemas.model import ValuesModel

PROFILES = {"shallow": {1: 1.0}, "deep": {5: 1.0}, "random": dict.fromkeys(range(1, 6), 1.0)}


def select_plan(chart: Chart, reference: dict[str, object], strength: int, level: int, seed: int) -> dict[str, object]:
    """
    Restrict each policy and its expansion candidates to the actual interaction plan.

    Args:
        chart (Chart): Fixed faulty fixture.
        reference (dict[str, object]): Complete independently verified population.
        strength (int): Requested interaction strength without exhaustive promotion.
        level (int): Fixed random and topology trim level.
        seed (int): Fixed selection seed.

    Returns:
        dict[str, object]: Reference with mapped selections and explicit planning statistics.
    """
    values = [mapping(value) for value in sequence(reference["values"])]
    positions = {configuration_key(value): index for index, value in enumerate(values)}
    started = time.perf_counter()
    plan = plan_interactions(
        ValuesModel.from_schema(chart.schema),
        strength,
        exhaustive_threshold=0,
        exhaustive_groups=(),
        max_cases=8192,
        max_candidates=1000000,
    )
    baseline = configuration_key(chart.defaults)
    planned = [
        chart.defaults,
        *(value for value in plan.values if configuration_key(value) != baseline),
    ]
    candidates = [positions[configuration_key(value)] for value in planned]
    selected, evidence = selections(chart, planned, level, seed, strength=strength)
    mapped = {name: [candidates[index] for index in indices] for name, indices in selected.items()}
    return {
        **reference,
        "candidate_indices": candidates,
        "selected_indices": mapped,
        "initial_selected_indices": mapped,
        "topology": evidence,
        "planning": {
            "requested_strength": strength,
            "effective_strength": plan.strength,
            "strategy": plan.strategy,
            "exhaustive_threshold": 0,
            "inferred_groups": False,
            "planned_inputs": len(planned),
            "seconds": time.perf_counter() - started,
        },
    }


def pooled_projection(references: list[dict[str, object]]) -> list[dict[str, object]]:
    """
    Fit one shared PCA frame across all structural-depth profiles within each topology family.

    Args:
        references (list[dict[str, object]]): Complete exact output populations.

    Returns:
        list[dict[str, object]]: Reproducible bases and coordinates keyed by fixture name.
    """
    frames: list[dict[str, object]] = []
    for family in ("uniform", "supported"):
        selected = [ref for ref in references if ref["family"] == family]
        bundles = []
        for ref in selected:
            outcomes = [mapping(value) for value in sequence(ref["outcomes"])]
            for identity in sequence(ref["outcome_indices"]):
                bundles.append([mapping(json.loads(str(encoded))) for encoded in sequence(outcomes[int(number(identity))]["resources"])])
        scores, basis = project(bundles)
        basis["fit"] = "pooled complete populations across depth profiles within this family"
        coordinates = {}
        offset = 0
        for ref in selected:
            count = len(sequence(ref["values"]))
            coordinates[str(ref["structure"])] = scores[offset : offset + count].tolist()
            offset += count
        frames.append({"family": family, "basis": basis, "coordinates": coordinates})
    return frames


def main(argv: list[str] | None = None, *, workspace: FixtureWorkspace | None = None) -> int:
    """
    Render new depth-distribution references and publish matched policy and PCA comparisons.

    Args:
        argv (list[str] | None): Explicit command arguments or the process command line.
        workspace (FixtureWorkspace | None): Explicit owner of the invocation's reusable chart.

    Returns:
        int: Zero for complete comparisons; one for an execution deadline.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("benchmarks/runs/nesting"))
    parser.add_argument("--permutations", type=int, default=8)
    parser.add_argument("--time-limit", type=parse_time_limit, default=540.0)
    parser.add_argument("--helm", default="helm")
    parser.add_argument("--plot-only", action="store_true")
    args = parser.parse_args(argv)
    from hypothesis_helm.benchmarking.reporting.nesting import plot

    if args.plot_only:
        plot(args.output, mapping(json.loads((args.output / "results.json").read_text())))
        return 0
    if not 1 <= args.permutations <= 10 or not 0 < args.time_limit <= 540:
        parser.error("require strength 1..10 and an execution ceiling <=9m")
    helm = shutil.which(args.helm)
    if not helm:
        parser.error("Helm is required")
    if (args.output / "results.json").exists():
        parser.error("results already exist; choose another output or --plot-only")
    args.output.mkdir(parents=True, exist_ok=True)
    references: list[dict[str, object]] = []
    rows: list[dict[str, object]] = []
    document: dict[str, object] = {
        "metadata": {
            "profiling": profile_settings(),
            "helm": Processes().run([helm, "version", "--short"], capture_output=True, check=True, timeout=30).stdout.strip(),
            "code_sha256": code_digest(),
            "permutations": args.permutations,
            "input_complexity": 10,
            "topology_components": 12,
            "topology_seed": 2026,
            "error_percent": 5,
            "error_seed": 1729,
            "seed": 2026,
            "trim_level": 2,
            "time_limit_seconds": args.time_limit,
            "method": "fresh references; replay selections; physically rerender additions",
            "budget": "reference and added renders share fixture ceiling; analysis excluded",
        },
        "references": references,
        "rows": rows,
    }
    for family in ("uniform", "supported"):
        for profile, weights in PROFILES.items():
            name = f"{family}-{profile}"
            print(f"{name}: depth distribution {weights}, strength {args.permutations}", flush=True)
            reference = run_case(
                args.output,
                name,
                10,
                5,
                1729,
                2026,
                2,
                helm,
                args.time_limit,
                topology_components=12,
                topology_seed=2026,
                topology_weights={"dependencies": 1, "interactions": 1, "equivalence": 1} if family == "supported" else None,
                topology_depth_weights=weights,
                workspace=workspace,
            )
            reference.update({"family": family, "profile": profile})
            if reference["status"] == "complete":
                chart = Chart.load(chart_path(args.output / "charts" / name, workspace=workspace))
                reference = select_plan(chart, reference, args.permutations, 2, 2026)
                rows.extend(
                    compare(
                        chart,
                        reference,
                        helm,
                        args.time_limit - number(reference["execution_seconds"]),
                    )
                )
            # The pooled frame below supersedes the per-fixture PCA and full-domain selections.
            for key in ("pca", "coordinates", "strategies"):
                reference.pop(key, None)
            references.append(reference)
            (args.output / "results.json").write_text(json.dumps(document) + "\n")
            if reference["status"] != "complete" or any(row["status"] != "complete" for row in rows):
                return 1
            print("  complete", flush=True)
    document["frames"] = pooled_projection(references)
    (args.output / "results.json").write_text(json.dumps(document) + "\n")
    plot(args.output, document)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
