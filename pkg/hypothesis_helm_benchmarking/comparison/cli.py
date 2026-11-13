"""
Prepare, measure and report matched backend comparisons through one command group.
"""

from __future__ import annotations

import argparse
import importlib
import logging
import os
import platform
import time
from pathlib import Path
from typing import TYPE_CHECKING

from hypothesis_helm_benchmarking.comparison.measure import measure
from hypothesis_helm_benchmarking.comparison.model import BACKENDS, Hardware, Lane, Workload, read_lanes, read_workload, save
from hypothesis_helm_benchmarking.comparison.report import report

if TYPE_CHECKING:
    from hypothesis_helm_benchmarking.charts.fixture import FixtureWorkspace

__all__ = ("main",)
LOGGER = logging.getLogger(__name__)


def hardware(backend: str) -> Hardware:
    """
    Resolve non-identifying platform and selected compiler details once per lane.

    Args:
        backend (str): Explicit engine selected by the invocation.

    Returns:
        Hardware: Observed CPU allocation, runtime versions and accelerator model.

    Raises:
        ValueError: A GPU request has no actual GPU available.
    """
    import numpy

    accelerator, compiler = "CPU", "reference"
    if backend == "cpu-vector":
        compiler = str(importlib.import_module("numba").__version__)
    elif backend == "gpu":
        torch = importlib.import_module("torch")
        compiler = str(torch.__version__)
        if torch.cuda.is_available():
            accelerator = str(torch.cuda.get_device_name(0))
        elif torch.backends.mps.is_available():
            accelerator = "Apple MPS"
        else:
            raise ValueError("matched GPU comparison requires an actual CUDA or MPS device")
    return Hardware(
        platform.system(), platform.machine(), os.cpu_count() or 1, platform.python_version(), numpy.__version__, compiler, accelerator
    )


def main(argv: list[str] | None = None, *, workspace: FixtureWorkspace | None = None) -> int:
    """
    Dispatch one deterministic workload preparation, measured lane or verified report.

    Args:
        argv (list[str] | None): Explicit arguments or the process command line.
        workspace (FixtureWorkspace | None): Parent command's invocation owner, unused by pure finite plans.

    Returns:
        int: Zero after complete validated output.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare", help="freeze one manifest before fanout")
    prepare.add_argument("--source", required=True)
    prepare.add_argument("--run", default="local")
    prepare.add_argument("--attempt", type=int, default=1)
    prepare.add_argument("--seed", type=int, default=2026)
    prepare.add_argument("--candidates", type=int, default=8192)
    prepare.add_argument("--factors", type=int, default=24)
    prepare.add_argument("--batches", type=int, nargs="+", default=[64, 256, 1024, 4096])
    prepare.add_argument("--repeats", type=int, default=5)
    prepare.add_argument("--output", type=Path, required=True)
    lane = commands.add_parser("measure", help="execute one actual backend without fallback")
    lane.add_argument("--input", type=Path, required=True)
    lane.add_argument("--backend", choices=BACKENDS, required=True)
    lane.add_argument("--require-device", choices=["reference", "cpu", "cuda", "mps"])
    lane.add_argument("--output", type=Path, required=True)
    publish = commands.add_parser("report", help="validate all lanes and render comparison plots")
    publish.add_argument("--input", type=Path, required=True)
    publish.add_argument("--lanes", type=Path, nargs="+", required=True)
    publish.add_argument("--output", type=Path, required=True)
    for operation in (lane, publish):
        operation.add_argument("--source", help="require the manifest to match this immutable source")
        operation.add_argument("--run", help="require the manifest to match this dispatch")
        operation.add_argument("--attempt", type=int, help="require the manifest to match this attempt")
    args = parser.parse_args(argv)
    LOGGER.info("Starting matched comparison operation=%s", args.command)
    if args.command == "prepare":
        workload = Workload(
            args.source, args.run, args.attempt, args.seed, args.candidates, args.factors, tuple(args.batches), args.repeats
        )
        workload.validate()
        save(args.output, workload)
        LOGGER.info("Completed matched comparison operation=prepare")
        return 0
    workload = read_workload(args.input)
    workload.validate()
    if any(
        expected is not None and expected != actual
        for expected, actual in ((args.source, workload.source), (args.run, workload.run), (args.attempt, workload.attempt))
    ):
        raise ValueError("matched workload belongs to a different source, run or attempt")
    if args.command == "measure":
        result = measure(workload, args.backend, hardware(args.backend), time.perf_counter)
        if args.require_device is not None and result.device != args.require_device:
            raise ValueError("observed backend device differs from the required hardware")
        save(args.output, result)
    else:
        lanes: list[Lane] = []
        for path in args.lanes:
            lanes.extend(read_lanes(path))
        report(workload, tuple(lanes), args.output)
    LOGGER.info("Completed matched comparison operation=%s", args.command)
    return 0
