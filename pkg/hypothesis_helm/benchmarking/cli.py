"""
Dispatch installed benchmark commands without depending on a source checkout.
"""

import argparse
import importlib
import os
import sys
import tempfile
from contextlib import nullcontext
from pathlib import Path

from hypothesis_helm.benchmarking.charts.fixture import FixtureWorkspace, chart_path
from hypothesis_helm.benchmarking.execution.profiling import PROFILE_DIRECTORY, capture
from hypothesis_helm.execution.signals import Termination
from hypothesis_helm.integrations.sharding import parse_shard_option, resolve_shard

COMMANDS = {
    "generate": "charts.generator",
    "run": "studies.performance",
    "discovery": "studies.discovery",
    "sparsity": "studies.sparsity",
    "structural-sparsity": "studies.structural_sparsity",
    "matrix": "studies.matrix",
    "pca": "studies.pca",
    "expansion": "studies.expansion",
    "structure-depth": "studies.structure_depth",
    "nesting": "studies.nesting",
    "stress": "studies.stress",
    "sampling": "studies.sampling",
    "calibration": "studies.calibration",
    "filtering": "studies.filtering",
    "error-surface": "studies.error_surface",
    "polynomial-surface": "studies.polynomial_surface",
    "symbolic-surface": "studies.symbolic_surface",
    "topology": "studies.topology",
    "flamegraph": "reporting.flamegraph",
}


def main(argv: list[str] | None = None) -> int:
    """
    Forward command arguments to the packaged benchmark entry point.

    Args:
        argv (list[str] | None): Explicit arguments or the process command line.

    Returns:
        int: Selected command's exit status.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile", type=Path, help="capture Python call stacks and flame graphs under this directory; place before COMMAND"
    )
    parser.add_argument("--parameters", type=Path, help="use a retained chart recipe with run, discovery, or sparsity")
    parser.add_argument("command", choices=COMMANDS)
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    try:
        module = importlib.import_module(f"hypothesis_helm.benchmarking.{COMMANDS[args.command]}")
        arguments = list(args.arguments)
        entry = getattr(module, "main", None) or module.run

        def invoke() -> int:
            """
            Keep one chart alive until the selected command and its workers finish.

            Returns:
                int: Selected benchmark command exit status.
            """
            from hypothesis_helm.benchmarking.charts.generator import reproduce

            with Termination(), nullcontext() if args.command == "generate" else FixtureWorkspace() as workspace:
                if args.parameters is not None and "--plot-only" not in args.arguments:
                    if args.command not in {"run", "discovery", "sparsity"}:
                        parser.error("global --parameters applies to run, discovery, or sparsity")
                    settings = argparse.ArgumentParser(add_help=False)
                    settings.add_argument("--output", type=Path)
                    settings.add_argument("--chart", type=Path)
                    settings.add_argument("--shard", type=parse_shard_option, default="auto")
                    options, _ = settings.parse_known_args(args.arguments)
                    if options.chart is not None:
                        parser.error("choose either --parameters or --chart")
                    if options.output is None:
                        options.output = Path("benchmarks/runs") / args.command
                        arguments.extend(["--output", str(options.output)])
                    destination = options.output
                    if args.command == "run":
                        shard, _ = resolve_shard(options.shard, os.environ)
                        if shard:
                            destination = destination / f"shard-{shard.name}"
                    logical = destination / "chart"
                    reproduce(args.parameters, logical, workspace=workspace)
                    arguments.extend(["--chart", str(chart_path(logical, workspace=workspace))])
                return int(entry(arguments, workspace=workspace))

        if args.profile is not None:
            from hypothesis_helm.benchmarking.reporting.flamegraph import render_profiles

            if args.command == "flamegraph":
                parser.error("flamegraph redraws existing profiles; use --profile with a benchmark study")
            args.profile.mkdir(parents=True, exist_ok=True)
            directory = Path(tempfile.mkdtemp(prefix="profile-", dir=args.profile)).resolve()
            previous_directory = os.environ.get(PROFILE_DIRECTORY)
            os.environ[PROFILE_DIRECTORY] = str(directory)
            print(f"Python profiles: {directory} (timings include profiling overhead)", file=sys.stderr)
            try:
                return capture(invoke, directory, "coordinator", {"command": args.command, "arguments": args.arguments})
            finally:
                if previous_directory is None:
                    os.environ.pop(PROFILE_DIRECTORY, None)
                else:
                    os.environ[PROFILE_DIRECTORY] = previous_directory
                interrupted = sys.exc_info()[0] is not None
                try:
                    render_profiles(directory, directory / "flamegraphs")
                except Exception as exc:
                    if not interrupted:
                        raise
                    print(f"Could not draw flame graphs: {exc}; completed captures remain in {directory}", file=sys.stderr)
        return invoke()
    except ModuleNotFoundError as exc:
        if exc.name is not None and exc.name.split(".")[0] in {"numpy", "matplotlib"}:
            parser.error('install benchmark dependencies with pip install "hypothesis-helm[benchmarking]"')
        raise
