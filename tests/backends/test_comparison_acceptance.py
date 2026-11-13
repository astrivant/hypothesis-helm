"""
Require the matched performance workload to execute on the selected real backend.
"""

from __future__ import annotations

import time

from hypothesis_helm_benchmarking.comparison.cli import hardware
from hypothesis_helm_benchmarking.comparison.measure import measure
from hypothesis_helm_benchmarking.comparison.model import Workload, validate_lane


def test_matched_workload_uses_selected_native_backend(native_backend: str) -> None:
    """
    Replay cold and steady worker requests using the actual selected engine.

    Args:
        native_backend (str): Explicit reference, compiled CPU or GPU CI lane.

    Returns:
        None: The real worker agrees with the independent oracle without fallback.
    """
    workload = Workload("1" * 40, "local", candidates=32, factors=8, batches=(8, 32), repeats=2)
    lane = measure(workload, native_backend, hardware(native_backend), time.perf_counter)
    validate_lane(workload, lane)
    assert lane.backend == native_backend
