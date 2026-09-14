"""
Compare filtering as one combined topology fixture is reduced in fixed increments.
"""

import argparse
import csv
import json
import shutil
from pathlib import Path

from attrs import asdict, evolve
from cattrs import Converter

from hypothesis_helm.benchmarking.analysis.selection import explanation
from hypothesis_helm.benchmarking.charts.fixture import FixtureWorkspace, chart_path
from hypothesis_helm.benchmarking.charts.generator import generate
from hypothesis_helm.benchmarking.charts.parameters import Parameters
from hypothesis_helm.benchmarking.charts.stress import FAMILIES, Stress, progression, stress_manifests
from hypothesis_helm.benchmarking.execution.profiling import profile_settings
from hypothesis_helm.benchmarking.execution.provenance import code_digest
from hypothesis_helm.benchmarking.reporting.plots import finish
from hypothesis_helm.benchmarking.studies.matrix import STRATEGIES, measure, reference_space
from hypothesis_helm.charts import yamlio
from hypothesis_helm.charts.model import Chart
from hypothesis_helm.execution.processes import Processes
from hypothesis_helm.reporting.budget import parse_time_limit
from hypothesis_helm.schemas.contracts import mapping, number, sequence


def plot(output: Path, document: dict[str, object]) -> None:
    """
    Plot real render cost and known-defect recall against the fixed parameter progression.

    Args:
        output (Path): Study results directory.
        document (dict[str, object]): Measured rows and their control values.

    Returns:
        None: PNG, SVG, CSV, and a concise explanatory table are written.
    """
    from matplotlib import pyplot as plt
    from matplotlib.ticker import MaxNLocator

    rows = [mapping(row) for row in sequence(document["rows"])]
    figure, axes = plt.subplots(1, 2, figsize=(13, 5))
    for strategy in STRATEGIES:
        selected = [row for row in rows if row["strategy"] == strategy]
        steps = [int(number(row["step"])) for row in selected]
        axes[0].plot(steps, [row["render_invocations"] for row in selected], "o-", label=strategy)
        axes[1].plot(
            steps,
            [
                100 * len(sequence(row["defects_found"])) / int(number(row["total_defects"])) if row["total_defects"] else 0
                for row in selected
            ],
            "o-",
            label=strategy,
        )
    axes[0].set(ylabel="Helm renders", xlabel="Fixed reduction step")
    axes[1].set(ylabel="Known defect families found (%)", xlabel="Fixed reduction step", ylim=(-2, 105))
    for axis in axes:
        axis.xaxis.set_major_locator(MaxNLocator(integer=True))
        axis.grid(alpha=0.2)
        axis.legend(fontsize=8)
    finish(
        figure,
        output,
        "topology-stress",
        "One control decreases by one per step. Time-limited rows show partial work; see the table for completion status.",
    )
    columns = (
        "step",
        "case",
        "strategy",
        "valid_domain",
        "selected",
        "completed",
        "render_invocations",
        "total_erroneous_inputs",
        "erroneous_inputs_evaluated",
        "erroneous_inputs_rendered",
        "status",
        "execution_seconds",
        "initial_selected",
        "expand_failures",
        "additional_scheduled",
        "sample_eligible",
        "sample_retained",
        "sample_minimum",
        "sample_minimum_fields",
        "profile_match",
        "sampling_fallback",
        "calibration_id",
    )
    with (output / "results.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    lines = [
        "# Topology stress progression",
        "",
        "One parameter decreases by one at each step; seeds and defect triggers remain fixed.",
        "",
        "![Render cost and defect recall](topology-stress.png)",
        "",
        "| Step | Parameter change | Strategy | Renders | Defects found / total | Erroneous inputs evaluated / total | Status |",
        "| --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['step']} | {row['case']} | {row['strategy']} | {row['render_invocations']} | "
            f"{len(sequence(row['defects_found']))} / {row['total_defects']} | "
            f"{row['erroneous_inputs_evaluated']} / {row['total_erroneous_inputs']} | "
            f"{row['status']} |"
        )
    lines.extend(
        [
            "",
            "Evaluated inputs include exact-equivalence reuse. CSV records physically rendered erroneous inputs separately.",
            "Coupled input constraints currently cause conservative compiler fallback; those rows measure that limitation.",
            "The input fields stay fixed. Removing constraints changes the valid-input denominator; "
            "reducing equivalence can increase render cost.",
            "Time-limited rows are incomplete measurements. This is a designed stress case, not a proven mathematical maximum.",
            "",
            "[Case parameters](cases/) | [Measurements](results.csv)",
            "",
        ]
    )
    lines.extend(explanation(rows))
    (output / "README.md").write_text("\n".join(lines))


def main(argv: list[str] | None = None, *, workspace: FixtureWorkspace | None = None) -> int:
    """
    Compile successive settings into one chart and measure the existing pruning policies.

    Args:
        argv (list[str] | None): Explicit command arguments or the process command line.
        workspace (FixtureWorkspace | None): Explicit owner of the invocation's reusable chart.

    Returns:
        int: Zero for completed or censored measurements; one for an oracle disagreement.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("benchmarks/runs/stress"))
    parser.add_argument("--parameters", type=Path, help="starting chart parameter file with stress controls")
    parser.add_argument("--steps", type=int, help="measure only this many steps from the fixed progression")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--trim-level", type=int, default=2)
    parser.add_argument("--time-limit", type=parse_time_limit, default=540.0, help="execution ceiling per strategy and step (default: 9m)")
    parser.add_argument("--helm", default="helm")
    parser.add_argument("--generate-only", action="store_true", help="save the complete parameter progression without measuring")
    parser.add_argument("--plot-only", action="store_true")
    args = parser.parse_args(argv)
    if args.plot_only:
        plot(args.output, mapping(json.loads((args.output / "results.json").read_text())))
        return 0
    if not 0 < args.time_limit <= 540 or args.trim_level < 0 or (args.steps is not None and args.steps < 1):
        parser.error("require a ceiling in (0, 9m], nonnegative trim, and a positive step count")
    parameters = Parameters(input_complexity=12, output_bins=4, stress=Stress())
    if args.parameters:
        source = mapping(yamlio.load(args.parameters.read_text()))
        converter = Converter(forbid_extra_keys=True)
        converter.register_structure_hook(Stress, lambda value, _: Stress(**value))
        parameters = converter.structure(source.get("parameters", source), Parameters)
    if parameters.stress is None:
        parser.error("starting parameters must define stress controls")
    if (args.output / "results.json").exists():
        parser.error("output already contains measurements; choose another directory")
    helm = shutil.which(args.helm)
    if helm is None and not args.generate_only:
        parser.error("Helm is required")
    args.output.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    document: dict[str, object] = {
        "metadata": {
            "profiling": profile_settings(),
            "chart_definition": "common parameterized benchmark chart",
            "code_sha256": code_digest(),
            "seed": args.seed,
            "time_limit_seconds": args.time_limit,
            "time_limit_scope": "per strategy per step",
            "helm": Processes().run([helm, "version", "--short"], capture_output=True, check=True, timeout=30).stdout.strip()
            if helm and not args.generate_only
            else None,
            "fault_families": list(FAMILIES),
            "starting_parameters": asdict(parameters),
            "strategies": list(STRATEGIES),
        },
        "rows": rows,
    }
    for index, (name, settings) in enumerate(progression(parameters.stress)[: args.steps]):
        logical = args.output / "charts" / name
        spec = generate(logical, **asdict(evolve(parameters, stress=settings), recurse=False), workspace=workspace)
        if args.generate_only:
            continue
        assert helm is not None
        chart = Chart.load(chart_path(logical, workspace=workspace))
        reference = reference_space(chart, spec, 4096)
        erroneous = sum(
            any(
                mapping(resource["data"])["status"] == "incorrect"
                for resource in stress_manifests(mapping(json.loads(value)), settings)
                if str(mapping(resource["metadata"])["name"]).startswith("defect-")
            )
            for value in reference[0]
        )
        for strategy in STRATEGIES:
            print(f"{name}: {strategy}", flush=True)
            row = measure(
                chart,
                spec,
                strategy,
                level=args.trim_level,
                seed=args.seed,
                limit=4096,
                seconds=args.time_limit,
                helm=helm,
                reference=reference,
            )
            row.update(
                step=index,
                case=name,
                parameters=asdict(settings),
                total_erroneous_inputs=erroneous,
                total_defects=len(FAMILIES) if settings.faults_enabled else 0,
            )
            rows.append(row)
            (args.output / "results.json").write_text(json.dumps(document, indent=2) + "\n")
            if row["status"] == "failed":
                return 1
    if not args.generate_only:
        plot(args.output, document)
    return 0
