"""
Dispatch installed benchmark commands without depending on a source checkout.
"""

import argparse
import importlib
import os
import sys
import tempfile
from pathlib import Path

from hypothesis_helm.benchmarking.profiling import PROFILE_DIRECTORY, capture

COMMANDS = {
    "generate": "generate_benchmark_chart",
    "run": "benchmark_helm",
    "discovery": "benchmark_discovery",
    "sparsity": "benchmark_sparsity",
    "matrix": "benchmark_matrix",
    "pca": "benchmark_pca",
    "expansion": "benchmark_expansion",
    "topology-depth": "benchmark_topology_depth",
    "nesting": "benchmark_nesting",
    "topology": "benchmark_topology",
    "flamegraph": "flamegraph",
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
    parser.add_argument("command", choices=COMMANDS)
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    previous = sys.argv
    try:
        module = importlib.import_module(f"hypothesis_helm.benchmarking.{COMMANDS[args.command]}")
        sys.argv = [f"{parser.prog} {args.command}", *args.arguments]
        entry = getattr(module, "main", None) or module.run
        if args.profile is not None:
            from hypothesis_helm.benchmarking.flamegraph import render_profiles

            if args.command == "flamegraph":
                parser.error("flamegraph redraws existing profiles; use --profile with a benchmark study")
            args.profile.mkdir(parents=True, exist_ok=True)
            directory = Path(tempfile.mkdtemp(prefix="profile-", dir=args.profile)).resolve()
            previous_directory = os.environ.get(PROFILE_DIRECTORY)
            os.environ[PROFILE_DIRECTORY] = str(directory)
            print(f"Python profiles: {directory} (timings include profiling overhead)", file=sys.stderr)
            try:
                return capture(lambda: int(entry()), directory, "coordinator", {"command": args.command, "arguments": args.arguments})
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
        return int(entry())
    except ModuleNotFoundError as exc:
        if exc.name is not None and exc.name.split(".")[0] in {"numpy", "matplotlib"}:
            parser.error('install benchmark dependencies with pip install "hypothesis-helm[benchmarking]"')
        raise
    finally:
        sys.argv = previous
