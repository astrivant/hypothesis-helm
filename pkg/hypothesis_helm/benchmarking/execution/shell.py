"""
Run packaged Bash benchmark helpers with the active environment's installed commands.
"""

import argparse
import os
import sys
from importlib.resources import as_file, files
from pathlib import Path

from hypothesis_helm.benchmarking.charts.fixture import FixtureWorkspace
from hypothesis_helm.execution.processes import Processes


def main(argv: list[str] | None = None, *, workspace: FixtureWorkspace | None = None) -> int:
    """
    Dispatch a maintained shell recipe without requiring repository-relative helper paths.

    Args:
        argv (list[str] | None): Helper name followed by its literal command arguments.
        workspace (FixtureWorkspace | None): Unused chart owner supplied by the benchmark dispatcher.

    Returns:
        int: Owned shell process exit status, with descendants joined before returning.
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("helper", choices=("smoke", "shards"))
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    resource = files("hypothesis_helm.benchmarking").joinpath("scripts", f"{args.helper}.sh")
    environment = dict(os.environ, PATH=f"{Path(sys.executable).parent}{os.pathsep}{os.environ.get('PATH', '')}")
    with as_file(resource) as script:
        return Processes().run(["bash", str(script), *args.arguments], env=environment).returncode
