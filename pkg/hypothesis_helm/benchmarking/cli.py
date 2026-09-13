"""
Dispatch installed benchmark commands without depending on a source checkout.
"""

import argparse
import importlib
import sys

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
    parser.add_argument("command", choices=COMMANDS)
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    previous = sys.argv
    try:
        module = importlib.import_module(f"hypothesis_helm.benchmarking.{COMMANDS[args.command]}")
        sys.argv = [f"{parser.prog} {args.command}", *args.arguments]
        entry = getattr(module, "main", None) or module.run
        return int(entry())
    except ModuleNotFoundError as exc:
        if exc.name is not None and exc.name.split(".")[0] in {"numpy", "matplotlib"}:
            parser.error('install benchmark dependencies with pip install "hypothesis-helm[benchmarking]"')
        raise
    finally:
        sys.argv = previous
